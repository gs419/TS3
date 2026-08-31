"""WorldModel: one fused picture of the sim, fed by both the Player.log event
stream and the Communication Port position feed.

- Log events (via LogInterpreter) drive phase/clearance/roster/scoring.
- Port snapshots (CMD_REQUEST_AIRPLANES/AIRPORT) fill in live geometry
  (pos, heading, speed, lat/lon) on the same Plane objects, keyed by callsign.
- Derived detectors run each port tick and emit geometric events
  (e.g. 'compression') that policies can subscribe to — the same on_event
  channel the log uses.

This is the layer the geometric features need: go-around revectoring,
compression/spacing, and 'cleared direct' all read live pos from here.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from gamestate import GameState, LogInterpreter, Plane, Phase

# game local meters per nautical mile
_M_PER_NM = 1852.0


@dataclass
class WorldModel:
    on_event: Callable[[str, Plane], None] = lambda k, p: None
    state: GameState = field(default_factory=GameState)
    center: Optional[tuple] = None      # (lat, lon) airport center
    magvar_deg: float = 0.0
    # compression thresholds
    min_spacing_nm: float = 3.0
    _prev_gap: dict = field(default_factory=dict)  # (lead,trail)->nm

    def __post_init__(self):
        self.log = LogInterpreter(self.state, self.on_event)

    # ---- inputs -------------------------------------------------------
    def feed_log(self, line: str) -> None:
        self.log.feed(line)

    def ingest_airport(self, airport: dict) -> None:
        lat = airport.get("_centerlat"); lon = airport.get("_centerlon")
        if lat is not None and lon is not None:
            self.center = (lat, lon)

    def ingest_airplanes(self, planes: list[dict]) -> None:
        """Update Plane geometry from a CMD_REQUEST_AIRPLANES snapshot, then run
        detectors."""
        now = time.monotonic()
        seen = set()
        for p in planes:
            cs = p.get("name")
            if not cs:
                continue
            seen.add(cs)
            plane = self.state.plane(cs)
            plane.pos = p.get("pos")
            plane.heading = (p.get("rot") or {}).get("y")
            plane.speed = p.get("spd")
            plane.state_int = p.get("state")
            plane.target_runway = self._rwy(p.get("trgrw"))
            if plane.pos:
                plane.alt_ft = plane.pos.get("y")
                plane.latlon = self._to_latlon(plane.pos)
            plane.updated = now
        self._detect_compression(seen)

    # ---- derived detectors -------------------------------------------
    def _detect_compression(self, seen: set) -> None:
        """Among airborne aircraft heading to the same runway, find in-trail
        pairs whose spacing is below min and shrinking, and emit 'compression'
        on the trailing aircraft."""
        by_rwy: dict[str, list[Plane]] = {}
        for cs in seen:
            pl = self.state.planes[cs]
            if pl.pos and pl.target_runway and self._airborne(pl):
                by_rwy.setdefault(pl.target_runway, []).append(pl)
        for rwy, group in by_rwy.items():
            if len(group) < 2:
                continue
            # order by distance to airport center as a threshold proxy
            group.sort(key=lambda p: self._range_nm(p.pos, {"x": 0, "y": 0, "z": 0}))
            for lead, trail in zip(group, group[1:]):
                gap = self._range_nm(lead.pos, trail.pos)
                key = (lead.callsign, trail.callsign)
                closing = gap < self._prev_gap.get(key, gap + 1)
                self._prev_gap[key] = gap
                if gap < self.min_spacing_nm and closing:
                    trail.last_transmission = f"COMPRESSION {gap:.1f}nm behind {lead.callsign}"
                    self.on_event("compression", trail)

    # ---- geometry helpers --------------------------------------------
    def _to_latlon(self, pos: dict):
        if not self.center:
            return None
        lat0, lon0 = self.center
        return (lat0 + pos["z"] / 111_320.0,
                lon0 + pos["x"] / (111_320.0 * math.cos(math.radians(lat0))))

    @staticmethod
    def _range_nm(a: dict, b: dict) -> float:
        dx = a["x"] - b["x"]; dz = a["z"] - b["z"]
        return math.hypot(dx, dz) / _M_PER_NM

    def bearing_to_latlon(self, plane: Plane, fix_latlon: tuple) -> Optional[int]:
        """Magnetic heading from a plane to a fix — powers 'cleared direct'."""
        if not (plane.pos and self.center):
            return None
        from phraseology import latlon_to_local, bearing_local
        fx = latlon_to_local(fix_latlon[0], fix_latlon[1], self.center)
        return bearing_local(plane.pos, fx, self.magvar_deg)

    @staticmethod
    def _rwy(trgrw):
        return str(trgrw) if trgrw not in (None, 0, "0") else None

    @staticmethod
    def _airborne(pl: Plane) -> bool:
        # airborne if it has altitude or non-trivial speed (state enum refined
        # once arrival states are identified from a live capture)
        return (pl.alt_ft or 0) > 50 or (pl.speed or 0) > 30


class WorldRunner:
    """Drives a WorldModel live: tails the log and polls the port in one loop."""

    def __init__(self, world: WorldModel, port_client, log_path: str,
                 poll_hz: float = 2.0):
        self.world = world
        self.pc = port_client
        self.log_path = log_path
        self.period = 1.0 / poll_hz

    def run(self):
        import os
        # prime airport center
        try:
            self.world.ingest_airport(self.pc.airport())
        except Exception as e:
            print(f"[world] airport read failed: {e}")
        f = open(self.log_path, "r", encoding="utf-8", errors="replace")
        f.seek(0, os.SEEK_END)
        last_poll = 0.0
        while True:
            line = f.readline()
            if line:
                self.world.feed_log(line)
            now = time.monotonic()
            if now - last_poll >= self.period:
                try:
                    self.world.ingest_airplanes(self.pc.airplanes())
                except Exception as e:
                    print(f"[world] port poll failed: {e}")
                last_poll = now
            if not line:
                time.sleep(0.05)
