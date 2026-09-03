"""Regression test for CommandArbiter runway keying and de-confliction.

The runway key must be the same for every clearance on one runway, or the
"one runway-occupying clearance per runway per tick" rule silently fails:
"RUNWAY 15 CLEARED TO LAND" and "RUNWAY 15 LINE UP AND WAIT" once keyed as
'15C' and '15L' (the side-letter regex ate the next word's first letter), so
the arbiter would forward a landing clearance AND a line-up on the same
runway in the same tick.

Run: python test_arbiter.py
"""
from __future__ import annotations

from arbiter import CommandArbiter, PRIO_CLEARANCE


class _Cap:
    def __init__(self):
        self.sent = []

    def send(self, t):
        self.sent.append(t)


def test_runway_key_ignores_following_word():
    p = CommandArbiter._parse
    assert p("s", 1, "X RUNWAY 15 CLEARED TO LAND", 1).runway == "15"
    assert p("s", 1, "X RUNWAY 15 LINE UP AND WAIT", 1).runway == "15"
    assert p("s", 1, "X RUNWAY 15 CLEARED FOR TAKEOFF", 1).runway == "15"
    assert p("s", 1, "X CROSS RUNWAY 8", 1).runway == "8"
    assert p("s", 1, "X RUNWAY 27L CLEARED TO LAND", 1).runway == "27L"
    assert p("s", 1, "X RUNWAY 27 L CLEARED TO LAND", 1).runway == "27L"


def test_one_occupying_clearance_per_runway_per_tick():
    snd = _Cap()
    arb = CommandArbiter(snd, aircraft_cooldown_s=0, runway_cooldown_s=0)
    a = arb.proposer("arrival", PRIO_CLEARANCE)
    d = arb.proposer("departure", PRIO_CLEARANCE)
    a.send("SKW6353 RUNWAY 15 CLEARED TO LAND")
    d.send("UPS87 RUNWAY 15 LINE UP AND WAIT")
    rec = arb.resolve(now=100.0)
    assert snd.sent == ["SKW6353 RUNWAY 15 CLEARED TO LAND"], snd.sent
    assert any("runway 15 already cleared" in r for _, r in rec["dropped"]), rec


def test_runway_cooldown_spans_clearance_types():
    snd = _Cap()
    arb = CommandArbiter(snd, aircraft_cooldown_s=0, runway_cooldown_s=12.0)
    a = arb.proposer("arrival", PRIO_CLEARANCE)
    d = arb.proposer("departure", PRIO_CLEARANCE)
    a.send("SKW6353 RUNWAY 15 CLEARED TO LAND"); arb.resolve(now=100.0)
    d.send("UPS87 RUNWAY 15 LINE UP AND WAIT"); rec = arb.resolve(now=105.0)
    assert snd.sent == ["SKW6353 RUNWAY 15 CLEARED TO LAND"], snd.sent
    assert any("cooldown" in r for _, r in rec["dropped"]), rec


if __name__ == "__main__":
    test_runway_key_ignores_following_word()
    test_one_occupying_clearance_per_runway_per_tick()
    test_runway_cooldown_spans_clearance_types()
    print("all arbiter regression tests PASSED")
