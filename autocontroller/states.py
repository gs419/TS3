"""AIRPLANES `state` enum -> phase, decoded from a live KBUR capture.

Sample (state -> speed kt / alt ft) that fixed the mapping:
  1: 250 / 4227   airborne, high (entry/descent)
  2: 220 / 2133   airborne, approach
  6: 221 / 1080   airborne, approach (lower)
  3: 130 / 30     short final / flare
  7: 130 / 9      flare / touchdown
  13: 45 / 0      ground, fast  (takeoff roll or landing rollout)
  14: 0.2 / 0     pushback / very slow
  8,9,12,15,16: 0 / 0   ground, stationary (gate/hold/taxi-stopped)

Speeds are in KNOTS (airborne range ~126..250) -> speed_to_mps = 0.514.
"""
from __future__ import annotations

KNOTS_TO_MPS = 0.514444

AIRBORNE = frozenset({1, 2, 3, 6, 7})       # in the air
APPROACH = frozenset({2, 3, 6, 7})          # inbound / on final (hot for a runway)
SHORT_FINAL = frozenset({3, 7})             # low, about to touch down
ROLLOUT = frozenset({13})                   # fast on the ground (takeoff roll / rollout)
GROUND_STATIONARY = frozenset({8, 9, 12, 15, 16})
PUSHBACK = frozenset({14})


def is_airborne(state) -> bool:
    return state in AIRBORNE


def is_on_final(state) -> bool:
    """Inbound/approaching a runway — the RWSL/compression 'hot' set."""
    return state in APPROACH


def occupies_runway(state) -> bool:
    """On the runway surface moving fast (takeoff roll or landing rollout)."""
    return state in ROLLOUT


def phase(state) -> str:
    if state in SHORT_FINAL: return "SHORT_FINAL"
    if state in AIRBORNE: return "AIRBORNE"
    if state in ROLLOUT: return "ROLLOUT"
    if state in PUSHBACK: return "PUSHBACK"
    if state in GROUND_STATIONARY: return "GROUND"
    return "UNKNOWN"
