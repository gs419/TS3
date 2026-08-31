"""Departure procedure (SID) data + selection.

Maps (airport, runway, destination) -> the initial departure instruction the
tower issues: initial climb altitude and an initial turn/heading. Optionally a
list of `legs` for the experimental "vector the SID" mode (issue successive
FLY HEADING / CLIMB TO before handoff — needs the live position feed to
sequence by fix proximity).

IMPORTANT — real-world data: the values in sids.json shipped here are EXAMPLES
/ placeholders so the mechanism is testable. Populate real SIDs from public
sources before relying on them:
  - FAA CIFP (Coded Instrument Flight Procedures), public domain:
    https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/cifp/
  - FAA d-TPP terminal procedure charts (the published SID plates).
Extract, per SID/runway: initial climb, initial heading or "runway heading",
and the first few fixes (lat/lon) for leg vectoring.

Scope note: in this sim the tower's authority ends at "contact departure".
The always-in-remit action is the INITIAL departure instruction (turn + climb),
which is what real towers issue before handing to departure. Flying the full
multi-leg SID means holding the aircraft on tower frequency and vectoring it
(FLY HEADING/CLIMB TO) leg by leg — supported by the AIR command set but
against the sim's normal handoff flow; treat it as an advanced, opt-in mode.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Leg:
    heading: Optional[int] = None      # magnetic heading to fly
    climb_ft: Optional[int] = None     # climb/maintain
    until_fix: Optional[str] = None    # fix name (needs nav data + position feed)
    note: str = ""


@dataclass
class Departure:
    sid: str = ""
    runway: str = ""
    initial_climb_ft: int = 3000
    # confirmed-phrasing initial action: either an "on course" turn or a heading
    turn_on_course: Optional[str] = None   # "LEFT" / "RIGHT"
    initial_heading: Optional[int] = None  # explicit fly-heading
    legs: list[Leg] = field(default_factory=list)  # optional vector-mode legs

    def takeoff_clearance(self, runway: str) -> str:
        """Build a CLEARED FOR TAKEOFF line with the initial departure folded in,
        using only phrasings observed in real logs / commands.csv."""
        parts = [f"RUNWAY {runway} CLEARED FOR TAKEOFF"]
        if self.turn_on_course:
            parts.append(f"AFTER DEPARTURE TURN {self.turn_on_course} ON COURSE")
        parts.append(f"ON REACHING ALTITUDE {self.initial_climb_ft} CONTACT DEPARTURE")
        return " ".join(parts)

    def vector_commands(self) -> list[str]:
        """Advanced mode: successive AIR commands to fly the SID legs before
        handoff. Requires the live position feed to decide when each leg is
        complete; this just returns the ordered instruction texts."""
        out = []
        for leg in self.legs:
            if leg.heading is not None:
                out.append(f"FLY HEADING {leg.heading:03d}")
            if leg.climb_ft is not None:
                out.append(f"CLIMB TO {leg.climb_ft}")
        out.append("CONTACT DEPARTURE")
        return out


class SidBook:
    """Loads sids.json and selects a departure for a flight."""

    def __init__(self, path: Optional[str] = None):
        path = path or os.path.join(os.path.dirname(__file__), "sids.json")
        self.data = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)

    def select(self, icao_airport: str, runway: str,
               dest: Optional[str] = None) -> Optional[Departure]:
        ap = self.data.get(icao_airport, {})
        rwys = ap.get("runways", {})
        r = rwys.get(runway) or rwys.get(runway.rstrip("LRC"))
        if not r:
            return None
        # per-destination override, else default
        chosen = None
        if dest and dest in r.get("by_dest", {}):
            chosen = r["by_dest"][dest]
        chosen = chosen or r.get("default")
        if not chosen:
            return None
        legs = [Leg(**lg) for lg in chosen.get("legs", [])]
        return Departure(
            sid=chosen.get("sid", ""),
            runway=runway,
            initial_climb_ft=chosen.get("initial_climb_ft", 3000),
            turn_on_course=chosen.get("turn_on_course"),
            initial_heading=chosen.get("initial_heading"),
            legs=legs,
        )
