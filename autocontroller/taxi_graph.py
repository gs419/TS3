"""Build a routable taxiway graph from the port's CMD_REQUEST_AIRPORT roads[].

Each road is a polyline of `knots` (nodes with pos{x,y,z}). Roads connect where
their knot positions coincide, so we merge knots within a small radius into
shared graph nodes (robust; does not depend on the raw `idx` semantics). Edges
are consecutive knots within a road, tagged with the road name and a class
(taxiway / runway / gate) so the router can price runway crossings and find
gates.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

_RUNWAY_RE = re.compile(r"^\d{1,2}[LRC]?$")
_MERGE_M = 22.0  # knots closer than this are the same node (taxiway width scale)


def road_class(name: str, rtype: int) -> str:
    if name.lower().startswith("gate"):
        return "gate"
    if _RUNWAY_RE.match(name):
        return "runway"
    return "taxiway"


@dataclass
class Edge:
    a: int            # node id
    b: int            # node id
    road: str         # taxiway/runway name
    rclass: str       # taxiway | runway | gate
    length: float     # meters


@dataclass
class TaxiGraph:
    nodes: list = field(default_factory=list)          # id -> (x, z)
    edges: list = field(default_factory=list)          # Edge
    adj: dict = field(default_factory=dict)            # node -> list[edge idx]
    gate_node: dict = field(default_factory=dict)      # gate name -> node id
    runway_nodes: dict = field(default_factory=dict)   # runway name -> [node ids]

    # ---- build -------------------------------------------------------
    @classmethod
    def from_airport(cls, airport: dict) -> "TaxiGraph":
        g = cls()
        for road in airport.get("roads", []):
            name = road.get("name", "")
            rclass = road_class(name, road.get("type", 0))
            knot_nodes = []
            for k in road.get("knots", []):
                p = k.get("pos", {})
                nid = g._node_at(p.get("x", 0.0), p.get("z", 0.0))
                knot_nodes.append(nid)
                if rclass == "gate":
                    g.gate_node.setdefault(name, nid)
                if rclass == "runway":
                    g.runway_nodes.setdefault(name, []).append(nid)
            for a, b in zip(knot_nodes, knot_nodes[1:]):
                if a == b:
                    continue
                g._add_edge(a, b, name, rclass)
        return g

    def stitch(self, snap_m: float = 38.0, passes: int = 3) -> "TaxiGraph":
        """Connect the graph where a taxiway meets another road mid-segment (its
        junction knot doesn't coincide with a knot on the other road). For each
        node near another edge's segment, split that edge at the node. Rebuilds
        adjacency each pass. Returns self."""
        for _ in range(passes):
            self._rebuild_adj()
            changed = False
            for n in range(len(self.nodes)):
                px, pz = self.nodes[n]
                for ei, e in enumerate(self.edges):
                    if e.a == n or e.b == n:
                        continue
                    q, t = self._project(px, pz, e.a, e.b)
                    if 0.05 < t < 0.95 and math.dist((px, pz), q) <= snap_m:
                        # split edge e at node n (n adopts the junction)
                        self.edges[ei] = Edge(e.a, n, e.road, e.rclass,
                                              math.dist(self.nodes[e.a], self.nodes[n]))
                        self.edges.append(Edge(n, e.b, e.road, e.rclass,
                                               math.dist(self.nodes[n], self.nodes[e.b])))
                        changed = True
                        break
            if not changed:
                break
        self._rebuild_adj()
        return self

    def _project(self, px, pz, a, b):
        ax, az = self.nodes[a]; bx, bz = self.nodes[b]
        dx, dz = bx - ax, bz - az
        L2 = dx * dx + dz * dz
        if L2 == 0:
            return (ax, az), 0.0
        t = ((px - ax) * dx + (pz - az) * dz) / L2
        t = max(0.0, min(1.0, t))
        return (ax + t * dx, az + t * dz), t

    def _rebuild_adj(self):
        self.adj = {}
        for i, e in enumerate(self.edges):
            self.adj.setdefault(e.a, []).append(i)
            self.adj.setdefault(e.b, []).append(i)

    def _node_at(self, x: float, z: float) -> int:
        for i, (nx, nz) in enumerate(self.nodes):
            if (nx - x) ** 2 + (nz - z) ** 2 <= _MERGE_M ** 2:
                return i
        self.nodes.append((x, z))
        return len(self.nodes) - 1

    def _add_edge(self, a: int, b: int, road: str, rclass: str):
        length = math.dist(self.nodes[a], self.nodes[b])
        idx = len(self.edges)
        self.edges.append(Edge(a, b, road, rclass, length))
        self.adj.setdefault(a, []).append(idx)
        self.adj.setdefault(b, []).append(idx)

    # ---- queries -----------------------------------------------------
    def nearest_node(self, x: float, z: float) -> Optional[int]:
        best, bd = None, 1e18
        for i, (nx, nz) in enumerate(self.nodes):
            d = (nx - x) ** 2 + (nz - z) ** 2
            if d < bd:
                best, bd = i, d
        return best

    def node_of(self, target: str) -> Optional[int]:
        """Resolve a gate name, runway name, or taxiway name to a node id."""
        if target in self.gate_node:
            return self.gate_node[target]
        if target in self.runway_nodes:
            return self.runway_nodes[target][len(self.runway_nodes[target]) // 2]
        for e in self.edges:              # any node on a named taxiway
            if e.road == target:
                return e.a
        return None

    def stats(self) -> dict:
        klass = {}
        for e in self.edges:
            klass[e.rclass] = klass.get(e.rclass, 0) + 1
        return {"nodes": len(self.nodes), "edges": len(self.edges),
                "by_class": klass, "gates": len(self.gate_node),
                "runways": sorted(self.runway_nodes)}
