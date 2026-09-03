"""Multi-position ATC: split an airport into controller positions (AI or human),
each owning areas/runways, with handoffs between them.

Grounded in the game's own model (from CMD_REQUEST_FREQS):
  - a frequency owns a set of areas: TOWER owns runway numbers ('24R'...),
    GROUND owns terminal groups, DEPARTURE owns 'departure'.
  - every aircraft carries `own` = its controlling frequency.
  - `CONTACT <freq>` hands an aircraft to another frequency (own changes).

A Position is a controller (AI or the human) that owns some areas/runways on a
frequency. Two handoff kinds:
  - cross-frequency  -> issue CONTACT <freq> (game tracks it via `own`)
  - same-frequency   -> virtual transfer inside our layer (e.g. splitting one
                        tower freq between AI-24R and human-24L); no game command
  - to a human       -> stand down + alert the human; they take it from there
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    name: str                       # "Sally", "Bob", "Human", "RampAI"
    role: str                       # local | ground | ramp | departure | clearance
    kind: str = "ai"                # ai | human
    frequency: str = ""             # game frequency string, e.g. "118.7"
    owns_runways: list = field(default_factory=list)   # ["24R"]
    owns_areas: list = field(default_factory=list)     # ["ramp","ground_east","TerminalA"]

    def owns(self, *, runway: Optional[str] = None, area: Optional[str] = None) -> bool:
        if runway and runway in self.owns_runways:
            return True
        if area and area in self.owns_areas:
            return True
        return False


@dataclass
class Handoff:
    when: str          # event key, e.g. "landed_on:24R", "holding_short:24L", "crossed:24L", "reached:ramp"
    to: Optional[str]  # target position name, or None = leaving the airport (departure/complete)
    frm: Optional[str] = None  # optional source constraint


@dataclass
class PositionMap:
    icao: str
    positions: dict          # name -> Position
    handoffs: list           # list[Handoff]

    def position(self, name: str) -> Optional[Position]:
        return self.positions.get(name)

    def responsible_for(self, *, runway=None, area=None) -> Optional[Position]:
        for p in self.positions.values():
            if p.owns(runway=runway, area=area):
                return p
        return None

    GROUND_ROLES = ("ground", "ramp", "clearance", "departure")

    def has_ai_ground(self) -> bool:
        """True if an AI position owns a ground-side role (pushback/taxi). When
        the human owns Ground, the AI must NOT issue departures — they are a
        ground function, not the tower/runway owner's job."""
        return any(p.kind == "ai" and p.role in self.GROUND_ROLES
                   for p in self.positions.values())

    def ai_owns_runway(self, runway: str) -> bool:
        """True if an AI (not human) local/clearance position owns this runway —
        the gate that keeps an AI controller off runways it isn't responsible
        for (human-owned, or another position's)."""
        p = self.responsible_for(runway=runway)
        return bool(p and p.kind == "ai")

    def owner_kind(self, runway: str) -> Optional[str]:
        p = self.responsible_for(runway=runway)
        return p.kind if p else None

    def handoff_for(self, event_key: str, frm: Optional[str]) -> Optional[Handoff]:
        for h in self.handoffs:
            if not self._event_matches(h.when, event_key):
                continue
            if h.frm in (None, frm):
                return h
        return None

    @staticmethod
    def _event_matches(pattern: str, event_key: str) -> bool:
        """Exact match, or a trailing '*' wildcard on the value after the colon
        (e.g. 'landed_on:*' matches 'landed_on:15')."""
        if pattern == event_key:
            return True
        if pattern.endswith(":*") and event_key.startswith(pattern[:-1]):
            return True
        return False

    @classmethod
    def load(cls, icao: str, path: Optional[str] = None) -> Optional["PositionMap"]:
        path = path or os.path.join(os.path.dirname(__file__), "positions.json")
        if not os.path.exists(path):
            return None
        data = json.load(open(path, encoding="utf-8")).get(icao)
        if not data:
            return None
        positions = {p["name"]: Position(**p) for p in data["positions"]}
        handoffs = [Handoff(when=h["when"], to=h.get("to"), frm=h.get("from"))
                    for h in data.get("handoffs", [])]
        return cls(icao, positions, handoffs)
