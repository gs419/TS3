"""Ground conflict detection: taxi conflicts, head-ons, pushback conflicts, and
runway incursions — from live positions (+ optional planned routes).

Keeps the multi-position ground layer safe at volume: when two aircraft would
occupy the same space, hold the lower-priority one; warn when an aircraft is
about to enter an active runway without a clearance.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Conflict:
    kind: str            # "converging" | "head_on" | "pushback" | "incursion"
    hold: str            # callsign to hold
    other: str           # the conflicting callsign / runway
    detail: str = ""


def _dist(a, b):
    return math.hypot(a["x"] - b["x"], a["z"] - b["z"])


def _closing(a, b):
    """True if a and b are getting closer, from positions + headings."""
    # vector a->b vs a's heading: if a moves toward b and b toward a -> closing
    def unit(h):
        r = math.radians(h or 0)
        return (math.sin(r), math.cos(r))  # x=east from heading
    abx, abz = b["pos"]["x"] - a["pos"]["x"], b["pos"]["z"] - a["pos"]["z"]
    ax, az = unit(a.get("heading"))
    bx, bz = unit(b.get("heading"))
    a_to_b = ax * abx + az * abz > 0          # a heading toward b
    b_to_a = bx * (-abx) + bz * (-abz) > 0     # b heading toward a
    return a_to_b and b_to_a


def _priority(p) -> int:
    """Lower = holds. Arrivals taxiing in yield to departures? Use: stopped
    yields less; here departures (going to runway) get priority over arrivals
    taxiing to gate, matching typical flow. Tune as needed."""
    role = p.get("role", "")
    return {"departure": 2, "arrival": 1}.get(role, 0)


def taxi_conflicts(planes, conflict_range_m: float = 150.0) -> list:
    """planes: list of {callsign, pos{x,z}, heading, speed, role}. Moving
    aircraft only. Returns conflicts with a recommended hold (lower priority)."""
    out = []
    moving = [p for p in planes if p.get("pos") and (p.get("speed") or 0) > 1]
    for i in range(len(moving)):
        for j in range(i + 1, len(moving)):
            a, b = moving[i], moving[j]
            if _dist(a["pos"], b["pos"]) > conflict_range_m:
                continue
            if not _closing(a, b):
                continue
            hold, other = (a, b) if _priority(a) <= _priority(b) else (b, a)
            hd = abs(((a.get("heading", 0) - b.get("heading", 0)) + 180) % 360 - 180)
            kind = "head_on" if hd > 135 else "converging"
            out.append(Conflict(kind, hold["callsign"], other["callsign"],
                                f"{_dist(a['pos'],b['pos']):.0f}m apart, "
                                f"hdg diff {hd:.0f}"))
    return out


def pushback_conflict(pusher, planes, arc_m: float = 80.0) -> Conflict | None:
    """Block a pushback if a moving aircraft is within arc_m behind the gate."""
    for p in planes:
        if p["callsign"] == pusher["callsign"] or not p.get("pos"):
            continue
        if (p.get("speed") or 0) > 1 and _dist(pusher["pos"], p["pos"]) < arc_m:
            return Conflict("pushback", pusher["callsign"], p["callsign"],
                            f"{_dist(pusher['pos'],p['pos']):.0f}m behind gate")
    return None


def runway_incursions(planes, rwsl_lights, hot_threshold_m: float = 60.0) -> list:
    """An aircraft near a RED hold-short point without a cross/takeoff clearance
    is a potential incursion. planes carry {cleared_onto: <rwy or None>}."""
    out = []
    reds = [l for l in rwsl_lights if l.state == "RED"]
    for p in planes:
        if not p.get("pos"):
            continue
        for l in reds:
            if math.hypot(p["pos"]["x"] - l.e, p["pos"]["z"] - l.n) < hot_threshold_m:
                if p.get("cleared_onto") not in l.runways:
                    out.append(Conflict("incursion", p["callsign"],
                                        "/".join(l.runways),
                                        "approaching hot hold-short uncleared"))
    return out
