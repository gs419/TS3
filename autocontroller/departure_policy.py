"""AI departure controller.

Drives a departure through: pushback -> taxi to runway -> line up -> takeoff
with the correct initial SID instruction -> contact departure. Rule-based and
conservative: one aircraft using a runway at a time, shared with the arrival
policy via the same GameState.runway_reserved_by.

Uses the same event stream as the arrival policy (subscribe on_event). Sender
is dry-run by default. Real taxi routing is intentionally minimal (single VIA);
extend with the airport `roads[]` graph from the port for full pathfinding.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto

from gamestate import GameState, Plane
from departures import SidBook


class DepPhase(Enum):
    NEW = auto()
    PUSHBACK = auto()
    TAXI = auto()
    LINEUP = auto()
    TAKEOFF = auto()
    HANDED_OFF = auto()


@dataclass
class DepState:
    callsign: str
    phase: DepPhase = DepPhase.NEW
    runway: str = ""
    dest: str = ""
    last_action: float = 0.0


@dataclass
class DeparturePolicy:
    state: GameState
    sender: object
    sids: SidBook = field(default_factory=SidBook)
    airport_icao: str = ""
    default_runway: str = ""          # set from CMD_REQUEST_STATUS/UICFG when live
    lineup_wait: bool = True
    enabled: bool = True

    _dep: dict[str, DepState] = field(default_factory=dict)

    # ---- event hook ---------------------------------------------------
    def on_event(self, kind: str, plane: Plane) -> None:
        if not self.enabled:
            return
        cs = plane.callsign
        if kind == "req_pushback":
            self._pushback(cs)
        elif kind == "req_taxi":
            self._taxi(cs)
        elif kind == "airborne":
            self._handoff(cs)
        elif kind == "runway_reserved":
            pass  # arrival/other took the runway; our tick() will wait

    # ---- periodic tick: advance lineup/takeoff ------------------------
    def tick(self) -> None:
        for cs, d in list(self._dep.items()):
            if d.phase == DepPhase.TAXI and self._runway_free(d.runway, cs):
                self._lineup(cs)
            elif d.phase == DepPhase.LINEUP and self._runway_free(d.runway, cs):
                self._takeoff(cs)

    # ---- steps --------------------------------------------------------
    def _pushback(self, cs: str):
        d = self._dep.setdefault(cs, DepState(cs))
        d.runway = d.runway or self.default_runway
        d.phase = DepPhase.PUSHBACK
        self._send(cs, f"PUSHBACK APPROVED EXPECT RUNWAY {d.runway}")

    def _taxi(self, cs: str):
        d = self._dep.setdefault(cs, DepState(cs))
        d.runway = d.runway or self.default_runway
        d.phase = DepPhase.TAXI
        # minimal routing; replace VIA with real path from roads[] graph
        self._send(cs, f"RUNWAY {d.runway}")

    def _lineup(self, cs: str):
        d = self._dep[cs]
        if not self.lineup_wait:
            return self._takeoff(cs)
        self.state.runway_reserved_by[d.runway] = cs
        d.phase = DepPhase.LINEUP
        self._send(cs, f"RUNWAY {d.runway} LINE UP AND WAIT")

    def _takeoff(self, cs: str):
        d = self._dep[cs]
        self.state.runway_reserved_by[d.runway] = cs
        d.phase = DepPhase.TAKEOFF
        dep = self.sids.select(self.airport_icao, d.runway, d.dest or None)
        if dep:
            self._send(cs, dep.takeoff_clearance(d.runway))
        else:
            self._send(cs, f"RUNWAY {d.runway} CLEARED FOR TAKEOFF")

    def _handoff(self, cs: str):
        d = self._dep.get(cs)
        if not d or d.phase == DepPhase.HANDED_OFF:
            return
        d.phase = DepPhase.HANDED_OFF
        self.state.runway_reserved_by.pop(d.runway, None)
        # CONTACT DEPARTURE is usually folded into the takeoff clearance;
        # issue it explicitly only if it wasn't.

    # ---- helpers ------------------------------------------------------
    def _runway_free(self, rwy: str, cs: str) -> bool:
        holder = self.state.runway_reserved_by.get(rwy)
        return holder in (None, cs)

    def _send(self, cs: str, text: str):
        self._dep[cs].last_action = time.monotonic()
        self.sender.send(f"{cs} {text}")
