"""Runway Status Lights (RWSL / Runway Entrance Lights) — live red/green state
per hold-short point.

A hold-short point is RED (do-not-enter) when any runway it protects is hot — an
arrival is too close, or an aircraft is rolling out / departing on it — else
GREEN. The occupancy timing is `runway_safety`; positions come from either:

  - the airport-builder export `<ICAO>.rwsl.json` (PREFERRED): surveyed hold
    positions with authoritative `runways` protection lists (see
    docs/RWSL-INTERFACE.md), or
  - the taxiway graph, as a fallback: entrance = a node shared by a runway edge
    and a taxiway edge, protecting that runway + its reciprocal.

Output serializes to the live feed the builder's planner ("Live RWSL" mode)
polls: [{e, n, state, reason}, ...].
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from runway_safety import RunwaySafety


@dataclass
class Hold:
    e: float                    # east (game-local metres) == graph x
    n: float                    # north (game-local metres) == graph z
    taxiway: str = ""
    runways: list = field(default_factory=list)   # runways this hold protects
    node: int = -1              # graph node id if graph-derived


@dataclass
class Light:
    e: float
    n: float
    state: str                  # "RED" | "GREEN"
    reason: str = ""
    taxiway: str = ""
    runways: list = field(default_factory=list)


class RWSL:
    def __init__(self, graph=None, safety: RunwaySafety | None = None,
                 holds: list | None = None):
        self.g = graph
        self.safety = safety or RunwaySafety()
        self.threshold = self._thresholds() if graph else {}
        self.holds = holds if holds is not None else (
            self._holds_from_graph() if graph else [])

    # ---- position sources -------------------------------------------
    @classmethod
    def from_positions_file(cls, path: str, graph=None,
                            safety: RunwaySafety | None = None) -> "RWSL":
        """Load surveyed holds from an airport-builder <ICAO>.rwsl.json export.
        Schema: {"icao":..., "holds":[{"e","n","taxiway","runways":[...]}, ...]}"""
        data = json.load(open(path, encoding="utf-8"))
        holds = [Hold(e=h["e"], n=h["n"], taxiway=h.get("taxiway", ""),
                      runways=list(h.get("runways", []))) for h in data["holds"]]
        return cls(graph=graph, safety=safety, holds=holds)

    def _holds_from_graph(self) -> list:
        node_classes = {}
        for e in self.g.edges:
            for nd in (e.a, e.b):
                node_classes.setdefault(nd, set()).add(e.rclass)
        holds = []
        for nd, cls in node_classes.items():
            if "runway" in cls and "taxiway" in cls:
                rwys = sorted({e.road for e in self.g.edges
                               if e.rclass == "runway" and nd in (e.a, e.b)})
                # a physical runway = both ends: add reciprocals
                rwys = sorted(set(rwys) | {self.reciprocal(r) for r in rwys})
                tw = next((e.road for e in self.g.edges
                           if e.rclass == "taxiway" and nd in (e.a, e.b)), "")
                x, z = self.g.nodes[nd]
                holds.append(Hold(e=x, n=z, taxiway=tw, runways=rwys, node=nd))
        return holds

    def _thresholds(self) -> dict:
        return {r: self.g.nodes[ns[0]] for r, ns in self.g.runway_nodes.items()}

    @staticmethod
    def reciprocal(rwy: str) -> str:
        m = re.match(r"(\d{1,2})([LRC]?)", rwy)
        if not m:
            return rwy
        num = (int(m.group(1)) + 18 - 1) % 36 + 1
        side = {"L": "R", "R": "L", "C": "C", "": ""}[m.group(2)]
        return f"{num}{side}"

    # ---- live state --------------------------------------------------
    def compute(self, world) -> list:
        """Red/green for every hold, from live traffic."""
        # cache threats per runway this tick
        tcache = {}

        def threats(rwy):
            if rwy not in tcache:
                th = self.threshold.get(rwy, (0.0, 0.0))
                tcache[rwy] = self.safety.threats_for_runway(world, rwy, th)
            return tcache[rwy]

        lights = []
        for h in self.holds:
            state, reason = "GREEN", f"{'/'.join(h.runways)} clear"
            for rwy in h.runways:
                dec = self.safety.can_cross(runway=rwy, cross_point=(h.e, h.n),
                                            threats=threats(rwy))
                if not dec.allow:
                    state, reason = "RED", dec.reason
                    break
            lights.append(Light(h.e, h.n, state, reason, h.taxiway, h.runways))
        return lights

    def reds(self, world) -> list:
        return [l for l in self.compute(world) if l.state == "RED"]

    def feed(self, world) -> list:
        """Serialize to the shared live-feed spec (docs/RWSL-INTERFACE.md)."""
        return [{"e": round(l.e, 2), "n": round(l.n, 2),
                 "state": l.state, "reason": l.reason} for l in self.compute(world)]
