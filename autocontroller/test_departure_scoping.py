"""Regression test for the live failure: with a HUMAN Ground position the AI
issued pushback/taxi for every departure on its runway (a ground function),
and a speculative line-up reservation then blocked every arrival.

Replays the real live KBUR session (testdata/kbur_live_session.log, 48 pushback
requests) through the assembled engine and asserts:

  * human Ground: the AI issues NO PUSHBACK / taxi / LINE UP / TAKEOFF, does not
    reserve the runway for a departure, and still clears arrivals to land.
  * AI Ground: the AI DOES work departures (pushbacks appear).

Run: python test_departure_scoping.py
"""
from __future__ import annotations

import os
import re
import time

from config import Config
from orchestrator import Orchestrator
from positions import PositionMap, Position, Handoff

LOG = os.path.join(os.path.dirname(__file__), "testdata", "kbur_live_session.log")
RUNWAYS = ("8", "26", "15", "33")


class _Cap:
    def __init__(self): self.sent = []
    def send(self, text): self.sent.append(text)


def _map(ground_kind):
    return PositionMap("KBUR", {
        "Local": Position(name="Local", role="local", kind="ai", frequency="118.7",
                          owns_runways=list(RUNWAYS)),
        "Ground": Position(name="Ground", role="ground", kind=ground_kind,
                           frequency="123.9", owns_areas=["TerminalA", "TerminalB"]),
    }, [Handoff("landed_on:*", "Local", "Ground"), Handoff("reached:ramp", "Ground", None)])


def _replay(ground_kind):
    clk = type("C", (), {"t": 0.0})()
    time.monotonic = lambda: clk.t
    snd = _Cap()
    orch = Orchestrator(Config(airport_icao="KBUR", default_runway="15"),
                        sender=snd, pmap=_map(ground_kind))
    ts = re.compile(r"^(?:!)?(\d{2}):(\d{2}):(\d{2})")
    last = 0.0
    with open(LOG, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = ts.match(line)
            if m:
                h, mi, s = map(int, m.groups()); clk.t = h*3600+mi*60+s
            orch.feed_log(line)
            if clk.t - last >= 1.0:
                orch.tick(clk.t); last = clk.t
    return orch, snd.sent


def test_human_ground_no_departures_and_arrivals_cleared():
    orch, sent = _replay("human")
    dep = [t for t in sent if any(k in t for k in
           ("PUSHBACK", "LINE UP", "CLEARED FOR TAKEOFF")) or re.search(r"^\S+ RUNWAY \d+\s*$", t)]
    assert not dep, f"AI issued departure commands although Ground is human: {dep[:6]}"
    assert not any(k == "15" for k in orch.world.state.runway_reserved_by
                   if orch.world.state.runway_reserved_by.get(k) not in (None,)
                   and orch.world.state.runway_reserved_by[k] not in _arrivals(sent)), \
        f"a non-arrival holds the runway: {orch.world.state.runway_reserved_by}"
    cleared = [t for t in sent if "CLEARED TO LAND" in t]
    assert cleared, f"AI cleared no arrivals even though the runway was free: sent={sent[:8]}"


def _arrivals(sent):
    return {t.split()[0] for t in sent if "CLEARED TO LAND" in t}


def test_ai_ground_does_work_departures():
    _, sent = _replay("ai")
    pushbacks = [t for t in sent if "PUSHBACK" in t]
    assert pushbacks, "AI Ground should issue pushbacks for departure requests"


if __name__ == "__main__":
    test_human_ground_no_departures_and_arrivals_cleared()
    print("  ok human Ground: no AI departures, runway free, arrivals cleared")
    test_ai_ground_does_work_departures()
    print("  ok AI Ground: departures worked")
    print("all departure-scoping tests PASSED")
