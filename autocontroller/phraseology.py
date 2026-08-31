"""Phraseology macro layer: expand high-level ATC shorthand into the primitive
commands the game actually executes.

The game core only runs verbs in commands.csv (FLY HEADING, TURN ... HEADING,
CLIMB TO, ENTER FINAL RUNWAY, TURN ... ON COURSE, ...). Instructions like
"cleared direct FIX" or "climb via SID" are NOT native verbs and cannot be
added via CSV (the CSV is only the recognizer's vocabulary; behavior is
compiled into the game binary). So we translate them into primitives:

  cleared direct <fix>   -> FLY HEADING <bearing to fix>     (needs live pos)
  climb via <SID>        -> CLIMB TO / FLY HEADING legs        (from departures)
  expect vectors / rejoin-> ENTER FINAL RUNWAY <r> or heading sequence

"Direct" here means "fly the heading toward the fix", re-issued as the aircraft
drifts — an approximation of RNAV direct, not true LNAV. Exact direct-to would
need a binary mod that adds a waypoint-nav command to the flight model.
"""
from __future__ import annotations

import math
from typing import Optional


def bearing_local(plane_pos: dict, fix_local: tuple[float, float],
                  magvar_deg: float = 0.0) -> int:
    """Heading (deg, 1..360) from a plane at game-local pos {x,y,z} to a fix at
    game-local (x, z) meters. Game runways are magnetic, so pass magvar
    (east positive) to convert true->magnetic."""
    dx = fix_local[0] - plane_pos["x"]      # east
    dz = fix_local[1] - plane_pos["z"]      # north
    true = math.degrees(math.atan2(dx, dz)) % 360.0
    mag = (true - magvar_deg) % 360.0
    return int(round(mag)) or 360


def latlon_to_local(lat: float, lon: float, center: tuple[float, float]) -> tuple[float, float]:
    """Inverse of port_client.local_to_latlon: lat/lon -> game-local (x=east,
    z=north) meters, using the airport center."""
    lat0, lon0 = center
    x = math.radians(lon - lon0) * 111_320.0 * math.cos(math.radians(lat0))
    z = (lat - lat0) * 111_320.0
    return (x, z)


def cleared_direct(callsign: str, plane_pos: dict, fix_latlon: tuple[float, float],
                   center: tuple[float, float], climb_ft: Optional[int] = None,
                   magvar_deg: float = 0.0) -> list[str]:
    """Expand 'cleared direct <fix>' into game commands. Needs the plane's live
    pos (from the port) and the airport center; fix coords from nav data."""
    fx = latlon_to_local(*fix_latlon, center)
    hdg = bearing_local(plane_pos, fx, magvar_deg)
    cmds = [f"{callsign} FLY HEADING {hdg:03d}"]
    if climb_ft:
        cmds.append(f"{callsign} CLIMB TO {climb_ft}")
    return cmds


def climb_via_sid(callsign: str, departure) -> list[str]:
    """Expand 'climb via <SID>' into the SID's leg commands (CLIMB TO / FLY
    HEADING ...). `departure` is a departures.Departure."""
    return [f"{callsign} {c}" for c in departure.vector_commands()]


# Macro registry: human shorthand -> a resolver that returns game commands.
# Geometric ones need `ctx` carrying live state (pos, center, magvar, fixes).
def expand(intent: str, callsign: str, ctx: dict) -> list[str]:
    """intent examples:
       'direct LARKS'            (ctx: pos, center, fixes, magvar[, climb])
       'climb via sid'           (ctx: departure)
       'rejoin final 26R'
    Returns concrete game command strings, or [] if it can't be expanded
    (e.g. missing live position)."""
    words = intent.strip().split()
    key = words[0].lower()

    if key == "direct" and len(words) >= 2:
        fix = words[1].upper()
        pos = ctx.get("pos"); center = ctx.get("center")
        fixes = ctx.get("fixes", {})
        if not (pos and center and fix in fixes):
            return []  # needs live pos + known fix
        return cleared_direct(callsign, pos, fixes[fix], center,
                              ctx.get("climb"), ctx.get("magvar", 0.0))

    if key == "climb" and "sid" in [w.lower() for w in words]:
        dep = ctx.get("departure")
        return climb_via_sid(callsign, dep) if dep else []

    if key == "rejoin" and len(words) >= 3:
        return [f"{callsign} ENTER FINAL RUNWAY {words[2].upper()}"]

    return []
