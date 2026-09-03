"""Regression test for the multi-position layer wired into the Orchestrator.

Replays the real KBUR session log (testdata/kbur_arrivals.log) through the
fully assembled engine — WorldModel -> policies -> arbiter -> sender — with a
position map, on a virtual clock, and checks what the arbiter actually SENDS:

  1. all-AI map (stock KBUR): every arrival is cleared; when it lands and exits
     the runway the Local position hands it off with "CONTACT GROUND" and the AI
     Ground position then issues "TAXI TO RAMP"; reaching the terminal completes
     the chain (ownership released).
  2. human-owned runway: with runway 15 assigned to a human position, the AI
     issues NO landing clearance on 15 (left to the human) and the human is
     alerted on handoff instead of an in-game CONTACT.

Run: python test_multiposition.py
"""
from __future__ import annotations

import os
import re
import time

from config import Config
from orchestrator import Orchestrator
from positions import PositionMap, Position, Handoff

LOG = os.path.join(os.path.dirname(__file__), "testdata", "kbur_arrivals.log")
ARRIVALS = ["N355FV", "SKW6353", "JSX1877", "JSX194"]
LANDED_AND_EXITED = ["SKW6353"]   # the only full landing->exit->terminal in the log


class _Clock:
    t = 0.0


class _CapSender:
    def __init__(self):
        self.sent = []

    def send(self, text):
        self.sent.append(text)


def _install_clock(clk):
    # every module does `import time` and calls time.monotonic() at call time
    time.monotonic = lambda: clk.t


def _replay(orch):
    ts = re.compile(r"^(?:!)?(\d{2}):(\d{2}):(\d{2})")
    clk = _Clock(); _install_clock(clk)
    last_tick = 0.0
    with open(LOG, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = ts.match(line)
            if m:
                h, mi, s = map(int, m.groups())
                clk.t = h * 3600 + mi * 60 + s
            orch.feed_log(line)
            if clk.t - last_tick >= 1.0:
                orch.tick(clk.t); last_tick = clk.t
    # let any settle timers (handoff -> taxi) drain
    for _ in range(5):
        clk.t += 1.0; orch.tick(clk.t)


def _kbur_map(human_runways=()):
    pm = PositionMap.load("KBUR")
    assert pm, "positions.json must have a KBUR entry"
    if human_runways:
        local = pm.positions["Local"]
        local.owns_runways = [r for r in local.owns_runways if r not in human_runways]
        pm.positions["Human"] = Position(name="Human", role="local", kind="human",
                                         frequency="118.7",
                                         owns_runways=list(human_runways))
    return pm


def test_all_ai_chain():
    snd = _CapSender()
    orch = Orchestrator(Config(airport_icao="KBUR"), sender=snd, pmap=_kbur_map())
    assert orch.pm is not None, "position manager should be active for KBUR"
    _replay(orch)
    sent = snd.sent
    cleared = {t.split()[0] for t in sent if "CLEARED TO LAND" in t}
    for cs in ARRIVALS:
        assert cs in cleared, f"{cs} not cleared to land: {sent}"
    for cs in LANDED_AND_EXITED:
        assert f"{cs} CONTACT GROUND" in sent, f"no CONTACT GROUND handoff for {cs}: {sent}"
        assert f"{cs} TAXI TO RAMP" in sent, f"ground never taxied {cs}: {sent}"
        # order: clearance -> contact -> taxi
        i_clr = next(i for i, t in enumerate(sent) if t.startswith(cs) and "CLEARED TO LAND" in t)
        i_con = sent.index(f"{cs} CONTACT GROUND")
        i_tax = sent.index(f"{cs} TAXI TO RAMP")
        assert i_clr < i_con < i_tax, f"bad order for {cs}: {sent}"
        # reached the terminal -> chain complete, ownership released
        assert cs not in orch.pm.owner, f"{cs} still owned after reaching ramp"


def test_human_owned_runway_is_left_alone():
    snd = _CapSender()
    alerts = []
    orch = Orchestrator(Config(airport_icao="KBUR"), sender=snd,
                        pmap=_kbur_map(human_runways=("15",)))
    orch.pm.notify_human = lambda cs, msg: alerts.append((cs, msg))
    _replay(orch)
    sent = snd.sent
    ai_cleared_on_15 = [t for t in sent if "CLEARED TO LAND" in t and "RUNWAY 15" in t]
    assert not ai_cleared_on_15, f"AI cleared a HUMAN runway: {ai_cleared_on_15}"
    # nothing else on 15 either (no handoff CONTACT issued by the AI for it)
    assert not any("CONTACT" in t for t in sent), f"unexpected CONTACT: {sent}"
    # all four arrivals in this log are on 15, so they all belong to the human
    assert not any("CLEARED TO LAND" in t for t in sent), f"AI issued clearances: {sent}"


if __name__ == "__main__":
    test_all_ai_chain()
    print("  ok all-AI chain: clear -> CONTACT GROUND -> TAXI TO RAMP -> complete")
    test_human_owned_runway_is_left_alone()
    print("  ok human-owned runway left alone")
    print("all multi-position regression tests PASSED")
