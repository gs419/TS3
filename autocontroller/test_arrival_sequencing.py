"""Regression test for the arrival-sequencing bug fixed after a live KBUR run.

Symptom (user report): "SKW6353 was clear of the runway but it never cleared the
next aircraft on final to land." Root causes, all covered here:

  1. Runway reservations were only released on GO AROUND / CONTACT DEPARTURE
     command echoes. A normal landing (or a post-touchdown flyaway) emits neither,
     so the reservation leaked and every later arrival was blocked forever.
     Fix: release off the game's landing-state machine (STATE CHANGE lines).
  2. The "RUNWAY 15 CLEARED" runway parser swallowed the 'C' of CLEARED,
     keying reservations as "15C" instead of "15".
  3. The next arrivals never even produced an `on_final` event because the
     heuristic callsign resolver couldn't map spoken forms like
     "big stripe eighteen seventy-seven". Fix: parse the game's own
     "speech airplanes:" dictionary for an exact spoken->ICAO map.
  4. In dry-run (no command is actually sent) an unconfirmed clearance was
     re-nagged forever, monopolizing the runway cooldown so the following
     arrival never got its turn. Fix: abandon after retries and free the cooldown.

Run: python test_arrival_sequencing.py
"""
from __future__ import annotations

import os
import re

import policy as P
from gamestate import GameState, LogInterpreter, PATTERNS
from policy import AutoTowerPolicy

LOG = os.path.join(os.path.dirname(__file__), "testdata", "kbur_arrivals.log")
ARRIVALS = ["N355FV", "SKW6353", "JSX1877", "JSX194"]


class _Clock:
    """Virtual clock so cooldowns/timeouts behave deterministically in replay."""
    t = 0.0

    def monotonic(self):
        return self.t


class _CapSender:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)


def _replay(pol, interp):
    ts = re.compile(r"^(?:!)?(\d{2}):(\d{2}):(\d{2})")
    last_tick = 0.0
    with open(LOG, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = ts.match(line)
            if m:
                h, mi, s = map(int, m.groups())
                P.time.t = h * 3600 + mi * 60 + s
            interp.feed(line)
            if P.time.t - last_tick >= 1.0:
                pol.tick()
                last_tick = P.time.t


def test_runway_parse_ignores_cleared():
    m = PATTERNS["runway_in_cmd"].search("N355FV RUNWAY 15 CLEARED TO LAND")
    assert m and m["num"] == "15" and not m["side"], "runway parsed as 15, not 15C"
    m = PATTERNS["runway_in_cmd"].search("AAL1 RUNWAY 27L CLEARED TO LAND")
    assert m and m["num"] == "27" and m["side"] == "L", "real side letter preserved"


def test_no_reservation_leak_and_all_on_final():
    events = []
    state = GameState()
    interp = LogInterpreter(state, lambda k, p: events.append((k, p.callsign)))
    with open(LOG, encoding="utf-8", errors="replace") as f:
        for line in f:
            interp.feed(line)
    on_final = {cs for k, cs in events if k == "on_final"}
    for cs in ARRIVALS:
        assert cs in on_final, f"{cs} never produced an on_final event"
    assert not state.runway_reserved_by, \
        f"runway reservation leaked: {state.runway_reserved_by}"
    freed = {cs for k, cs in events if k == "runway_cleared"}
    assert {"N355FV", "SKW6353"} <= freed, "landings/flyaways must free the runway"


def test_every_arrival_gets_cleared_in_sequence():
    P.time = _Clock()
    state = GameState()
    snd = _CapSender()
    pol = AutoTowerPolicy(state=state, sender=snd)
    interp = LogInterpreter(state, pol.on_event)
    _replay(pol, interp)
    issued = [t.split()[0] for t in snd.sent]
    for cs in ARRIVALS:
        assert cs in issued, f"{cs} was never cleared to land"
    # sequence: each arrival cleared only after earlier one; order preserved
    first_seen = [cs for i, cs in enumerate(issued) if cs not in issued[:i]]
    assert first_seen == ARRIVALS, f"unexpected clearance order: {first_seen}"


if __name__ == "__main__":
    test_runway_parse_ignores_cleared()
    test_no_reservation_leak_and_all_on_final()
    test_every_arrival_gets_cleared_in_sequence()
    print("all arrival-sequencing regression tests PASSED")
