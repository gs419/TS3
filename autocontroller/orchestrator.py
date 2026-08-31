"""Orchestrator — the assembled AI-ATC engine.

Wires the WorldModel (log + optional port position feed) to the controller
policies through the CommandArbiter, fans the event stream out to every policy
plus the scoring tuner and telemetry, and runs a tick loop. This is the single
entrypoint that turns the standalone modules into one coordinated system.

Dry-run by default (arbiter forwards to a DryRunSender). Swap in a real sender
once the write path is confirmed.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from config import Config
from worldmodel import WorldModel
from arbiter import CommandArbiter, PRIO_CLEARANCE
from policy import AutoTowerPolicy
from departure_policy import DeparturePolicy
from scoring_tuner import ScoringTuner
from telemetry import Telemetry
from senders import DryRunSender


@dataclass
class Orchestrator:
    config: Config
    sender: object = None
    subs: list = field(default_factory=list)

    def __post_init__(self):
        self.sender = self.sender or DryRunSender()
        self.arbiter = CommandArbiter(
            self.sender,
            aircraft_cooldown_s=self.config.aircraft_cooldown_s,
            runway_cooldown_s=self.config.arbiter_runway_cooldown_s)
        self.world = WorldModel(on_event=self._dispatch)
        self.world.magvar_deg = self.config.magvar_deg
        self.tuner = ScoringTuner()
        self.telemetry = Telemetry()

        self.arrival = AutoTowerPolicy(
            state=self.world.state,
            sender=self.arbiter.proposer("arrival", PRIO_CLEARANCE),
            runway_cooldown_s=self.config.runway_cooldown_s)
        self.departure = DeparturePolicy(
            state=self.world.state,
            sender=self.arbiter.proposer("departure", PRIO_CLEARANCE),
            airport_icao=self.config.airport_icao,
            default_runway=self.config.default_runway)

        # fan-out order: policies first, then learning/metrics
        self.subs = [self.arrival.on_event, self.departure.on_event,
                     self.tuner.on_event, self.telemetry.on_event]

    def _dispatch(self, kind, plane):
        for s in self.subs:
            s(kind, plane)

    # ---- inputs -------------------------------------------------------
    def feed_log(self, line: str):
        self.world.feed_log(line)

    def poll_port(self, port_client):
        try:
            if self.world.center is None:
                self.world.ingest_airport(port_client.airport())
            self.world.ingest_airplanes(port_client.airplanes())
        except Exception as e:
            print(f"[orch] port poll failed: {e}")

    # ---- per-tick -----------------------------------------------------
    def tick(self, now: float | None = None) -> dict:
        self.arrival.tick()
        self.departure.tick()
        result = self.arbiter.resolve(now)
        # feed learned adjustments back into live params
        self.config.apply_tunables(self.tuner.params)
        self.arrival.runway_cooldown_s = self.config.runway_cooldown_s
        self.departure.enabled = True
        return result

    # ---- live loop ----------------------------------------------------
    def run(self, log_path: str, port_client=None, poll_hz: float = 2.0):
        f = open(log_path, "r", encoding="utf-8", errors="replace")
        f.seek(0, os.SEEK_END)
        last_poll = last_tick = 0.0
        period = 1.0 / poll_hz
        print(f"[orch] running {self.config.airport_icao} "
              f"(dry_run={self.config.dry_run})")
        while True:
            line = f.readline()
            if line:
                self.feed_log(line)
            now = time.monotonic()
            if port_client and now - last_poll >= period:
                self.poll_port(port_client); last_poll = now
            if now - last_tick >= 1.0:
                self.tick(now); last_tick = now
            if not line:
                time.sleep(0.05)

    def status(self) -> dict:
        return {"telemetry": self.telemetry.report(),
                "tuner": self.tuner.report(),
                "config": self.config}
