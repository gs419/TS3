"""Runway Status Lights (RWSL / Runway Entrance Lights) — compute a red/green
state for every runway hold-short point, live.

Real RWSL turns the entrance lights RED at a taxiway/runway intersection when it
is unsafe to enter or cross because an aircraft is on the runway or an arrival is
close. That is exactly the `runway_safety` check, evaluated at each entrance
point. This module derives the entrance points from the airport taxiway graph
and lights them from the live WorldModel.

Output feeds an external display (a second-monitor ground/RWSL panel) — or a
binary mod that recolors the in-sim lights (see docs/DYNAMIC-LIGHTING.md).
"""
from __future__ import annotations

from dataclasses import dataclass

from runway_safety import RunwaySafety


@dataclass
class Light:
    runway: str
    node: int
    pos: tuple
    state: str          # "RED" (do not enter) | "GREEN" (clear)
    reason: str = ""


class RWSL:
    def __init__(self, graph, safety: RunwaySafety | None = None):
        self.g = graph
        self.safety = safety or RunwaySafety()
        self.entrances = self._find_entrances()          # runway -> [node ids]
        self.threshold = self._thresholds()              # runway -> (x,z)

    def _find_entrances(self):
        node_classes = {}
        for e in self.g.edges:
            for n in (e.a, e.b):
                node_classes.setdefault(n, set()).add(e.rclass)
        ent = {}
        for n, cls in node_classes.items():
            if "runway" in cls and "taxiway" in cls:
                for e in self.g.edges:
                    if e.rclass == "runway" and n in (e.a, e.b):
                        ent.setdefault(e.road, [])
                        if n not in ent[e.road]:
                            ent[e.road].append(n)
        return ent

    def _thresholds(self):
        th = {}
        for rwy, nodes in self.g.runway_nodes.items():
            # approach threshold ≈ one runway end; use the first runway node
            th[rwy] = self.g.nodes[nodes[0]]
        return th

    @staticmethod
    def reciprocal(rwy: str) -> str:
        """15 -> 33, 8 -> 26 (same physical runway, other end)."""
        import re
        m = re.match(r"(\d{1,2})([LRC]?)", rwy)
        if not m:
            return rwy
        num = (int(m.group(1)) + 18 - 1) % 36 + 1
        side = {"L": "R", "R": "L", "C": "C", "": ""}[m.group(2)]
        return f"{num}{side}"

    def compute(self, world) -> list:
        """Return the current light state for every runway entrance point. A
        physical runway (both reciprocal ends) is treated as one: traffic on
        either end lights all of its entrance points."""
        lights = []
        for rwy, nodes in self.entrances.items():
            threshold = self.threshold.get(rwy, (0.0, 0.0))
            # threats targeting this end OR its reciprocal (same strip)
            threats = self.safety.threats_for_runway(world, rwy, threshold)
            recip = self.reciprocal(rwy)
            if recip in self.threshold:
                threats += self.safety.threats_for_runway(world, recip, self.threshold[recip])
            for n in nodes:
                pos = self.g.nodes[n]
                dec = self.safety.can_cross(runway=rwy, cross_point=pos, threats=threats)
                lights.append(Light(rwy, n, pos,
                                    "GREEN" if dec.allow else "RED", dec.reason))
        return lights

    def reds(self, world) -> list:
        return [l for l in self.compute(world) if l.state == "RED"]
