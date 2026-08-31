"""Wake-turbulence separation minima by weight class.

TS3 exposes a weight class per aircraft (`wc` on strips as "L/M/H/J", on planes
as a small int). This gives the required in-trail separation behind a leader on
final (nm) and the runway wait after a departure (seconds). Values approximate
ICAO/FAA wake categories; tune to taste.
"""
from __future__ import annotations

# category order: L(light) M(medium) H(heavy) J(super)
_ALIASES = {"l": "L", "m": "M", "h": "H", "j": "J", "s": "J",
            "1": "L", "2": "M", "3": "H", "4": "J",
            "light": "L", "medium": "M", "heavy": "H", "super": "J"}

# required in-trail distance (nm) for FOLLOWER behind LEADER, arrivals
_ARR_NM = {
    ("J", "L"): 8, ("J", "M"): 7, ("J", "H"): 6, ("J", "J"): 4,
    ("H", "L"): 6, ("H", "M"): 5, ("H", "H"): 4, ("H", "J"): 4,
    ("M", "L"): 5, ("M", "M"): 3, ("M", "H"): 3, ("M", "J"): 3,
    ("L", "L"): 3, ("L", "M"): 3, ("L", "H"): 3, ("L", "J"): 3,
}
# required time (s) behind a departing LEADER before FOLLOWER may roll
_DEP_S = {
    ("J", "L"): 180, ("J", "M"): 180, ("J", "H"): 120, ("J", "J"): 90,
    ("H", "L"): 120, ("H", "M"): 120, ("H", "H"): 90, ("H", "J"): 90,
    ("M", "L"): 120, ("M", "M"): 60, ("M", "H"): 60, ("M", "J"): 60,
    ("L", "L"): 60, ("L", "M"): 60, ("L", "H"): 60, ("L", "J"): 60,
}


def category(wc) -> str:
    return _ALIASES.get(str(wc).strip().lower(), "M")


def arrival_spacing_nm(leader_wc, follower_wc) -> float:
    return _ARR_NM.get((category(leader_wc), category(follower_wc)), 3)


def departure_wait_s(leader_wc, follower_wc) -> int:
    return _DEP_S.get((category(leader_wc), category(follower_wc)), 60)
