"""Runway conflict check: is it safe to cross / enter an active runway now?

Answers the controller's question "can I clear this aircraft to cross 24L?" by
comparing, in TIME:
  - how long until the next arrival (or a departure/landing rollout) reaches the
    crossing point, vs.
  - how long the crossing aircraft needs to start rolling, cross the runway, and
    be fully clear on the far side.

Clear only if the soonest threat is farther out than the crossing takes, plus a
safety buffer. Otherwise HOLD until the arrival has passed or a big enough gap
opens. This is what stops MSG_RUNWAY_SEPARATION / MSG_GROUND_CRASH.

All inputs are live from the WorldModel (port position feed) + airport geometry
(runway threshold and the crossing point node from the taxi graph). Distances
are game-local meters; speed is the AIRPLANES `spd`. If speed units differ from
m/s on your build, set `speed_to_mps`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class CrossDecision:
    allow: bool
    reason: str
    margin_s: Optional[float] = None       # spare seconds (allow) / deficit (hold)
    threat: Optional[str] = None           # callsign of the limiting aircraft


@dataclass
class RunwaySafety:
    cross_clear_s: float = 30.0            # time for a jet to start, cross, and clear
    safety_buffer_s: float = 15.0         # extra margin
    approach_watch_s: float = 120.0       # ignore arrivals more than this far out
    speed_to_mps: float = 1.0             # AIRPLANES spd -> m/s (calibrate)
    min_speed_mps: float = 5.0            # treat slower as stopped

    def can_cross(self, *, runway: str, cross_point: tuple, threats: list) -> CrossDecision:
        """threats: list of dicts {callsign, pos{x,z}, speed, kind} where kind is
        'arrival' (airborne inbound), 'rollout' (landed, on runway), or
        'departure' (rolling for takeoff). cross_point is the (x,z) where the
        taxi route crosses this runway."""
        need = self.cross_clear_s + self.safety_buffer_s
        soonest = None
        for t in threats:
            eta = self._eta_to_point(t, cross_point)
            if eta is None:
                # on the runway but not moving toward/away meaningfully → occupied
                return CrossDecision(False, f"{runway} occupied by {t['callsign']} "
                                     f"({t.get('kind')})", None, t["callsign"])
            if t.get("kind") in ("rollout", "departure") and eta < need:
                return CrossDecision(False, f"{t['callsign']} {t['kind']} on {runway}",
                                     round(eta - need, 1), t["callsign"])
            if t.get("kind") == "arrival" and eta > self.approach_watch_s:
                continue  # too far to matter yet
            if soonest is None or eta < soonest[0]:
                soonest = (eta, t)
        if soonest is None:
            return CrossDecision(True, f"{runway} clear — no traffic in range", None)
        eta, t = soonest
        margin = eta - need
        if margin >= 0:
            return CrossDecision(True, f"clear: {t['callsign']} is {eta:.0f}s out, "
                                 f"crossing needs {need:.0f}s (margin {margin:.0f}s)",
                                 round(margin, 1), t["callsign"])
        return CrossDecision(False, f"HOLD: {t['callsign']} lands in {eta:.0f}s, "
                             f"crossing needs {need:.0f}s (short {-margin:.0f}s)",
                             round(margin, 1), t["callsign"])

    def _eta_to_point(self, threat: dict, point: tuple) -> Optional[float]:
        pos = threat.get("pos") or {}
        dx = point[0] - pos.get("x", 0.0)
        dz = point[1] - pos.get("z", 0.0)
        dist = math.hypot(dx, dz)
        spd = (threat.get("speed") or 0.0) * self.speed_to_mps
        if spd < self.min_speed_mps:
            # stopped on/near the runway: occupied if within a wingspan-ish of the
            # crossing point, else effectively no threat
            return None if dist < 60 else self.approach_watch_s + 1
        return dist / spd

    # ---- helper to build threats from the world model ----------------
    @staticmethod
    def threats_for_runway(world, runway: str, threshold: tuple) -> list:
        """Collect arrivals inbound to `runway` and aircraft on it from the
        WorldModel's live planes. `threshold` is the runway threshold (x,z)."""
        out = []
        for cs, pl in world.state.planes.items():
            if not pl.pos:
                continue
            tgt = pl.target_runway
            on_final = tgt == runway
            near_rwy = _dist(pl.pos, threshold) < 4000  # within ~2nm of threshold
            if on_final and (pl.alt_ft or 0) > 20:
                out.append({"callsign": cs, "pos": pl.pos, "speed": pl.speed or 0,
                            "kind": "arrival"})
            elif on_final and near_rwy:
                out.append({"callsign": cs, "pos": pl.pos, "speed": pl.speed or 0,
                            "kind": "rollout"})
        return out


def _dist(pos: dict, pt: tuple) -> float:
    return math.hypot(pos.get("x", 0) - pt[0], pos.get("z", 0) - pt[1])
