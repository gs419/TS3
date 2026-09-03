"""Orchestrator — the assembled AI-ATC engine.

Wires the WorldModel (log + optional port position feed) to the controller
policies through the CommandArbiter, fans the event stream out to every policy
plus the scoring tuner and telemetry, and runs a tick loop. This is the single
entrypoint that turns the standalone modules into one coordinated system.

Multi-position: when a PositionMap is available for the airport
(positions.json), every AI policy is scoped to the runways its position owns
(human-owned runways are left alone), and a PositionManager runs the handoff
chain — e.g. an arrival lands and exits the runway -> "CONTACT GROUND" -> the AI
ground position taxis it to the ramp -> complete.

Dry-run by default (arbiter forwards to a DryRunSender). Swap in a real sender
(PortCommandSender) to actually issue commands — see live.py.
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
from positions import PositionMap
from position_manager import PositionManager


@dataclass
class Orchestrator:
    config: Config
    sender: object = None
    pmap: object = None                 # PositionMap; auto-loaded if None
    handoff_settle_s: float = 2.0       # gap between CONTACT and the next controller's first call
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
            runway_cooldown_s=self.config.runway_cooldown_s,
            echo_timeout_s=8.0, max_retries=2)   # live: a missed injection is retried
        self.departure = DeparturePolicy(
            state=self.world.state,
            sender=self.arbiter.proposer("departure", PRIO_CLEARANCE),
            airport_icao=self.config.airport_icao,
            default_runway=self.config.default_runway)

        # ---- multi-position layer ----------------------------------------
        self.pm = None
        self._taxi_due: dict[str, float] = {}     # callsign -> when to issue taxi
        self._taxied: set = set()
        if self.pmap is None and self.config.airport_icao:
            self.pmap = PositionMap.load(self.config.airport_icao)
        if self.pmap:
            self.pm = PositionManager(
                self.pmap,
                sender=self.arbiter.proposer("handoff", PRIO_CLEARANCE),
                notify_human=self._notify_human,
                on_assign=self._on_assign)
            self.ground = self.arbiter.proposer("ground", PRIO_CLEARANCE)
            # AI controllers only touch runways an AI position is responsible for
            self.arrival.owns_runway = self.pmap.ai_owns_runway
            self.departure.owns_runway = self.pmap.ai_owns_runway
            # pushback/taxi/takeoff is a GROUND function: only run departures
            # when an AI position owns a ground-side role. If the human owns
            # Ground, the AI issues no departures (they are the human's).
            self.departure.enabled = self.pmap.has_ai_ground()
            if not self.departure.enabled:
                print('[orch] departures are HUMAN-owned (no AI ground position) '
                      '— AI will clear arrivals only')

        # fan-out order: policies first, then learning/metrics
        self.subs = [self.arrival.on_event, self.departure.on_event,
                     self.tuner.on_event, self.telemetry.on_event]

    def _dispatch(self, kind, plane):
        for s in self.subs:
            s(kind, plane)
        if self.pm:
            self._position_events(kind, plane)

    # ---- multi-position: ownership + handoffs ---------------------------
    def _position_events(self, kind, plane):
        cs = plane.callsign
        if kind == "on_final" and plane.runway:
            # an arrival enters under whoever owns its runway (AI or human)
            if cs not in self.pm.owner:
                pos = self.pm.assign_initial(cs, runway=plane.runway)
                if pos:
                    print(f"[pos] {cs} on final {plane.runway} -> {pos.name} "
                          f"({pos.kind} {pos.role})")
        elif kind == "landed" and plane.runway:
            self._log_handoff(self.pm.handle_event(f"landed_on:{plane.runway}", cs))
        elif kind == "reached_ramp":
            self._log_handoff(self.pm.handle_event("reached:ramp", cs))

    def _on_assign(self, cs, pos):
        """Ownership changed. When an AI ground/ramp position receives an
        aircraft, it issues the taxi — after a short settle so it doesn't
        collide with the CONTACT in the same arbiter tick."""
        if pos is None:
            self._taxied.discard(cs)
            self._taxi_due.pop(cs, None)
            return
        if pos.kind == "ai" and pos.role in ("ground", "ramp") and cs not in self._taxied:
            self._taxi_due[cs] = time.monotonic() + self.handoff_settle_s

    def _notify_human(self, cs, msg):
        print(f"\a[HUMAN] {cs}: {msg}")

    @staticmethod
    def _log_handoff(desc):
        if desc:
            print(f"[pos] handoff {desc}")

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
        self._flush_taxi(now if now is not None else time.monotonic())
        result = self.arbiter.resolve(now)
        drain = getattr(self.sender, "drain", None)
        if drain:
            drain()          # keep the command channel's receive window empty
        # feed learned adjustments back into live params
        self.config.apply_tunables(self.tuner.params)
        self.arrival.runway_cooldown_s = self.config.runway_cooldown_s
        return result

    def _flush_taxi(self, now: float):
        for cs, due in list(self._taxi_due.items()):
            if now >= due:
                del self._taxi_due[cs]
                self._taxied.add(cs)
                self.ground.send(f"{cs} TAXI TO RAMP")

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
