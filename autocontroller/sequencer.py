"""Arrival sequencer / metering.

Instead of clearing whoever is on final, order arrivals to a runway by distance
to the threshold and enforce the required in-trail spacing (wake minima). For
each follower that is too close, emit a metering action:
  - TIGHTEN the leader (MAKE SHORT APPROACH) if the follower is only slightly
    close and the leader can help, else
  - S-TURN / EXTEND the follower to open the gap (VFR/pattern), else
  - GO AROUND the follower when it's inside minimum and closing.
Distances are game-local metres from the port feed; spacing is in nm.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from separation import arrival_spacing_nm

_M_PER_NM = 1852.0


@dataclass
class SeqAction:
    callsign: str
    action: str          # "CLEAR" | "SHORT_APPROACH" | "EXTEND" | "GO_AROUND"
    detail: str = ""


def _dist_nm(pos, thr):
    tx, tz = (thr["x"], thr["z"]) if isinstance(thr, dict) else (thr[0], thr[1])
    return math.hypot(pos["x"] - tx, pos["z"] - tz) / _M_PER_NM


def sequence(runway: str, threshold, arrivals) -> list:
    """arrivals: list of dicts {callsign, pos{x,z}, wc}. Returns ordered
    SeqActions (nearest first). CLEAR means spacing behind the one ahead is OK."""
    ordered = sorted(
        [a for a in arrivals if a.get("pos")],
        key=lambda a: _dist_nm(a["pos"], threshold))
    actions = []
    prev = None
    for a in ordered:
        d = _dist_nm(a["pos"], threshold)
        if prev is None:
            actions.append(SeqAction(a["callsign"], "CLEAR",
                                     f"lead, {d:.1f}nm final"))
        else:
            gap = _dist_nm(a["pos"], prev["pos"])
            need = arrival_spacing_nm(prev.get("wc"), a.get("wc"))
            if gap >= need:
                actions.append(SeqAction(a["callsign"], "CLEAR",
                                         f"{gap:.1f}nm behind {prev['callsign']} "
                                         f"(need {need})"))
            else:
                short = need - gap
                if short <= 1.0:
                    act = "SHORT_APPROACH"   # ask the leader to tighten
                    who = prev["callsign"]
                elif d > 5:
                    act = "EXTEND"           # follower has room to stretch
                    who = a["callsign"]
                else:
                    act = "GO_AROUND"        # too tight, inside the slot
                    who = a["callsign"]
                actions.append(SeqAction(who, act,
                               f"{gap:.1f}nm behind {prev['callsign']}, "
                               f"need {need} (short {short:.1f}nm)"))
        prev = a
    return actions
