"""Clearance-deviation detection.

Compares an aircraft's live movement against what it was cleared to do and flags
deviations: wrong runway on final, or straying off an assigned taxi route.
Powers a safety alert (or a trainer's "you cleared them wrong" feedback).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Deviation:
    callsign: str
    kind: str            # "wrong_runway" | "off_route"
    detail: str


def _runway_heading(name: str) -> int:
    m = math.nan
    import re
    mm = re.match(r"(\d{1,2})", name or "")
    return int(mm.group(1)) * 10 if mm else 0


def wrong_runway(callsign, heading, cleared_runway, tol_deg: float = 25.0):
    """On final, the aircraft heading should match the cleared runway. A large
    mismatch means it's lining up on the wrong runway."""
    if heading is None or not cleared_runway:
        return None
    want = _runway_heading(cleared_runway)
    off = abs(((heading - want) + 180) % 360 - 180)
    if off > tol_deg:
        return Deviation(callsign, "wrong_runway",
                         f"hdg {heading:.0f} vs rwy {cleared_runway} ({want}), "
                         f"off {off:.0f}")
    return None


def off_route(callsign, pos, route_nodes, graph, tol_m: float = 60.0):
    """Distance from the assigned taxi route polyline; beyond tol = strayed."""
    if not pos or not route_nodes or len(route_nodes) < 2:
        return None
    best = 1e18
    for a, b in zip(route_nodes, route_nodes[1:]):
        ax, az = graph.nodes[a]; bx, bz = graph.nodes[b]
        best = min(best, _pt_seg((pos["x"], pos["z"]), (ax, az), (bx, bz)))
    if best > tol_m:
        return Deviation(callsign, "off_route",
                         f"{best:.0f}m off assigned route")
    return None


def _pt_seg(p, a, b):
    dx, dz = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dz * dz
    t = 0.0 if L2 == 0 else max(0, min(1, ((p[0]-a[0])*dx + (p[1]-a[1])*dz) / L2))
    qx, qz = a[0] + t * dx, a[1] + t * dz
    return math.hypot(p[0] - qx, p[1] - qz)
