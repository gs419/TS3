"""Wind-based active runway selection.

Ranks runways by headwind component from the live wind (STATUS/AIRPORT
`_winddir`/`_windspeed`), so the controllers use the into-wind runway and can
switch on a wind shift. Also reports crosswind/tailwind so a policy can flag
out-of-limits conditions.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass
class RunwayWind:
    runway: str
    heading: int          # runway magnetic heading (deg)
    headwind: float       # + into wind (good), - tailwind
    crosswind: float      # absolute crosswind component


def runway_heading(name: str) -> int:
    m = re.match(r"(\d{1,2})", name)
    return (int(m.group(1)) * 10) if m else 0


def rank_runways(runways, wind_dir: float, wind_speed: float) -> list:
    """Return runways ranked best-first (most headwind). `runways` is a list of
    names; reciprocals are treated as distinct (24L vs 6R are opposite ends)."""
    out = []
    for r in runways:
        hdg = runway_heading(r)
        diff = math.radians(wind_dir - hdg)
        head = wind_speed * math.cos(diff)
        cross = abs(wind_speed * math.sin(diff))
        out.append(RunwayWind(r, hdg, round(head, 1), round(cross, 1)))
    out.sort(key=lambda w: w.headwind, reverse=True)
    return out


def best_runway(runways, wind_dir: float, wind_speed: float,
                max_tailwind: float = 5.0, max_crosswind: float = 30.0):
    """Pick the best usable runway. Returns (RunwayWind, warnings)."""
    ranked = rank_runways(runways, wind_dir, wind_speed)
    if not ranked:
        return None, ["no runways"]
    top = ranked[0]
    warn = []
    if top.headwind < -max_tailwind:
        warn.append(f"{top.runway}: tailwind {-top.headwind:.0f} kt exceeds "
                    f"{max_tailwind:.0f}")
    if top.crosswind > max_crosswind:
        warn.append(f"{top.runway}: crosswind {top.crosswind:.0f} kt exceeds "
                    f"{max_crosswind:.0f}")
    return top, warn
