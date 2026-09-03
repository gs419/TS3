"""CommandArbiter — collects proposed commands from every policy each tick,
de-conflicts them, and forwards only the winners to the real sender.

Policies don't send directly; each is handed a `proposer(source, priority)`
that looks like a Sender (`.send(text)`) but buffers a Proposal. Once per tick
`resolve()` ranks the proposals by priority and drops conflicts:
  - one command per aircraft per tick (highest priority wins),
  - one runway-occupying clearance (land/takeoff/line-up/cross) per runway per
    tick,
  - per-aircraft and per-runway cooldowns so nothing is spammed.
Winners go to the real sender; drops are logged with a reason.

Priorities (higher wins): safety interventions > separation/sequencing >
routine clearances > advisories.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

# suggested priority bands
PRIO_SAFETY = 100      # go-around, cancel takeoff, incursion stop
PRIO_SEQUENCE = 60     # sequencing / spacing actions
PRIO_CLEARANCE = 40    # routine land/takeoff/taxi/handoff
PRIO_ADVISORY = 10

_RUNWAY_CLEARANCE = ("CLEARED TO LAND", "CLEARED FOR TAKEOFF",
                     "CLEARED FOR IMMEDIATE TAKEOFF", "LINE UP", "CROSS RUNWAY")


@dataclass
class Proposal:
    source: str
    priority: int
    text: str
    callsign: str = ""
    runway: str = ""
    occupies_runway: bool = False
    seq: int = 0


class _Proposer:
    def __init__(self, arbiter, source, priority):
        self._a = arbiter; self._src = source; self._prio = priority

    def send(self, text: str):
        self._a._propose(self._src, self._prio, text)


@dataclass
class CommandArbiter:
    sender: object
    aircraft_cooldown_s: float = 8.0
    runway_cooldown_s: float = 12.0
    _buf: list = field(default_factory=list)
    _seq: int = 0
    _last_aircraft: dict = field(default_factory=dict)   # cs -> (text, t)
    _last_runway: dict = field(default_factory=dict)      # rwy -> t
    log: list = field(default_factory=list)

    # ---- API for policies -------------------------------------------
    def proposer(self, source: str, priority: int) -> _Proposer:
        return _Proposer(self, source, priority)

    def _propose(self, source, priority, text):
        self._seq += 1
        self._buf.append(self._parse(source, priority, text, self._seq))

    # ---- per-tick resolution ----------------------------------------
    def resolve(self, now: float | None = None) -> dict:
        now = now if now is not None else time.monotonic()
        # highest priority first; stable by arrival order within a priority
        props = sorted(self._buf, key=lambda p: (-p.priority, p.seq))
        self._buf = []
        sent, dropped = [], []
        used_aircraft, used_runway = set(), set()
        for p in props:
            reason = self._reject(p, now, used_aircraft, used_runway)
            if reason:
                dropped.append((p, reason)); continue
            # commit
            self.sender.send(p.text)
            sent.append(p)
            used_aircraft.add(p.callsign)
            self._last_aircraft[p.callsign] = (p.text, now)
            if p.occupies_runway and p.runway:
                used_runway.add(p.runway)
                self._last_runway[p.runway] = now
        rec = {"sent": [p.text for p in sent],
               "dropped": [(d.text, r) for d, r in dropped]}
        self.log.append(rec)
        return rec

    def _reject(self, p, now, used_aircraft, used_runway):
        if p.callsign and p.callsign in used_aircraft:
            return f"aircraft {p.callsign} already commanded this tick"
        if p.occupies_runway and p.runway and p.runway in used_runway:
            return f"runway {p.runway} already cleared this tick"
        last = self._last_aircraft.get(p.callsign)
        if last and last[0] == p.text and now - last[1] < self.aircraft_cooldown_s:
            return f"duplicate of recent command to {p.callsign}"
        if (p.occupies_runway and p.runway and
                now - self._last_runway.get(p.runway, -1e9) < self.runway_cooldown_s):
            return f"runway {p.runway} cooldown"
        return None

    # ---- parse ------------------------------------------------------
    @staticmethod
    def _parse(source, priority, text, seq) -> Proposal:
        t = text.upper()
        cs = t.split()[0] if t.split() else ""
        # same rule as gamestate: a side letter only counts when standalone,
        # otherwise "RUNWAY 15 CLEARED" keys as 15C and "... LINE UP" as 15L and
        # the per-runway exclusion/cooldown never sees them as one runway.
        rm = re.search(r"RUNWAY\s+(\d{1,2})(?:\s*([LRC])(?![A-Z]))?", t)
        runway = (rm.group(1) + (rm.group(2) or "")) if rm else ""
        occ = any(k in t for k in _RUNWAY_CLEARANCE)
        return Proposal(source, priority, text, cs, runway, occ, seq)
