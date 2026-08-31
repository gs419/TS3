"""Ground router: shortest sensible taxi route over the TaxiGraph, with guidance.

Produces a route (node path), the taxiway-name sequence, the runway crossings
along it, and a ready-to-issue TS3 taxi clearance. Guidance knobs let a
controller (or you) shape the route:

  - via=[...]       force the route through these points/taxiways in order
                    ("Bob, take him via C then D")
  - avoid=[...]     never use these taxiways (closures/congestion)
  - prefer=[...]    bias toward these taxiways (cheaper)
  - runway_cross_penalty  cost added per runway crossing (default high, so the
                    router avoids crossing active runways unless necessary)
  - hold_short_of=[runways]  don't route across these at all (your runway)
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Optional

from taxi_graph import TaxiGraph


@dataclass
class RouteGuidance:
    via: list = field(default_factory=list)
    avoid: list = field(default_factory=list)
    prefer: list = field(default_factory=list)
    prefer_factor: float = 0.5          # multiply length on preferred taxiways
    runway_cross_penalty: float = 4000.0
    hold_short_of: list = field(default_factory=list)


@dataclass
class Route:
    ok: bool
    nodes: list = field(default_factory=list)
    taxiways: list = field(default_factory=list)     # ordered unique taxiway names
    crossings: list = field(default_factory=list)    # runway names crossed
    cost: float = 0.0
    reason: str = ""


class GroundRouter:
    def __init__(self, graph: TaxiGraph):
        self.g = graph

    # ---- public ------------------------------------------------------
    def route(self, start, goal, guidance: Optional[RouteGuidance] = None) -> Route:
        """start/goal may be node ids or names (gate/runway/taxiway)."""
        gd = guidance or RouteGuidance()
        s = self._nid(start); t = self._nid(goal)
        if s is None or t is None:
            return Route(False, reason=f"unresolved endpoint(s): {start!r}->{goal!r}")
        # don't taxi through other aircraft's gates: allow only the goal gate
        self._goal_gate = goal if isinstance(goal, str) and goal in self.g.gate_node else None
        waypoints = [s] + [self._nid(v) for v in gd.via] + [t]
        if any(w is None for w in waypoints):
            return Route(False, reason="unresolved via point")
        full = []
        total = 0.0
        for a, b in zip(waypoints, waypoints[1:]):
            leg = self._dijkstra(a, b, gd)
            if leg is None:
                return Route(False, reason=f"no path {a}->{b} (avoids/hold-short too strict?)")
            path, cost = leg
            full = full[:-1] + path if full else path
            total += cost
        return self._finish(self._smooth(full), total, gd)

    def _smooth(self, nodes: list) -> list:
        """Remove weaves: if two non-adjacent nodes on the path are joined by a
        direct edge no longer than the subpath between them, splice it out.
        Yields a physically shorter, non-backtracking route."""
        if len(nodes) < 3:
            return nodes
        changed = True
        while changed:
            changed = False
            for i in range(len(nodes) - 2):
                for j in range(len(nodes) - 1, i + 1, -1):
                    e = self._edge_between(nodes[i], nodes[j])
                    if not e:
                        continue
                    sub = sum(self._seg_len(nodes[k], nodes[k + 1])
                              for k in range(i, j))
                    if e.length <= sub + 1e-6:
                        nodes = nodes[:i + 1] + nodes[j:]
                        changed = True
                        break
                if changed:
                    break
        return nodes

    def _seg_len(self, a, b) -> float:
        e = self._edge_between(a, b)
        return e.length if e else 1e9

    def route_to_handoff(self, start, goal, blocking_runways,
                         guidance: Optional[RouteGuidance] = None):
        """Route toward `goal`, but if the natural path crosses one of
        `blocking_runways` (e.g. the human's runway), stop at the hold-short
        before the first such crossing and report which runway must be crossed.
        Returns (Route_to_holdshort, runway_to_cross | None). This is how Bob
        taxis an aircraft to hold short of your runway and hands it to you.
        """
        gd = guidance or RouteGuidance()
        # find the natural route allowing the crossing, to see where it crosses
        open_gd = RouteGuidance(via=gd.via, avoid=gd.avoid, prefer=gd.prefer,
                                prefer_factor=gd.prefer_factor,
                                runway_cross_penalty=gd.runway_cross_penalty,
                                hold_short_of=[])
        full = self.route(start, goal, open_gd)
        if not full.ok:
            return full, None
        crossed = next((r for r in full.crossings if r in blocking_runways), None)
        if not crossed:
            return full, None                      # no handoff needed
        # truncate the node path just before the first edge on `crossed`
        cut = len(full.nodes)
        for i, (a, b) in enumerate(zip(full.nodes, full.nodes[1:])):
            e = self._edge_between(a, b)
            if e and e.rclass == "runway" and e.road == crossed:
                cut = i + 1
                break
        partial = self._finish(full.nodes[:cut], 0.0, gd)
        partial.reason = f"hold short of {crossed}"
        return partial, crossed

    # ---- core --------------------------------------------------------
    def _dijkstra(self, s, t, gd: RouteGuidance):
        dist = {s: 0.0}; prev = {}; pq = [(0.0, s)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == t:
                break
            if d > dist.get(u, 1e18):
                continue
            for ei in self.g.adj.get(u, []):
                e = self.g.edges[ei]
                v = e.b if e.a == u else e.a
                w = self._edge_cost(e, gd)
                if w is None:
                    continue
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd; prev[v] = u
                    heapq.heappush(pq, (nd, v))
        if t not in dist:
            return None
        path = [t]
        while path[-1] != s:
            path.append(prev[path[-1]])
        path.reverse()
        return path, dist[t]

    def _edge_cost(self, e, gd: RouteGuidance) -> Optional[float]:
        if e.road in gd.avoid:
            return None
        if e.rclass == "runway" and e.road in gd.hold_short_of:
            return None                      # never cross your runway
        if e.rclass == "gate" and e.road != getattr(self, "_goal_gate", None):
            return None                      # don't taxi through other gates
        c = e.length
        if e.road in gd.prefer:
            c *= gd.prefer_factor
        if e.rclass == "runway":
            c += gd.runway_cross_penalty     # discourage crossings
        return c

    def _finish(self, nodes, cost, gd) -> Route:
        taxiways, crossings, last = [], [], None
        for a, b in zip(nodes, nodes[1:]):
            e = self._edge_between(a, b)
            if not e:
                continue
            if e.rclass == "runway":
                if e.road not in crossings:
                    crossings.append(e.road)
            elif e.road != last:
                taxiways.append(e.road); last = e.road
        taxiways = self._collapse_names(taxiways)
        return Route(True, nodes=nodes, taxiways=taxiways, crossings=crossings, cost=cost)

    @staticmethod
    def _collapse_names(via: list) -> list:
        """Readability pass for the spoken clearance (node path unchanged):
        collapse X Y X -> X (a name that flips to a junction spur and back), and
        drop consecutive duplicates. Turns 'B B5 B B1 B' into 'B'."""
        changed = True
        while changed and len(via) >= 3:
            changed = False
            for i in range(len(via) - 2):
                if via[i] == via[i + 2] and via[i] != via[i + 1]:
                    del via[i + 1:i + 3]
                    changed = True
                    break
        out = []
        for name in via:
            if not out or out[-1] != name:
                out.append(name)
        return out

    # ---- clearance text ---------------------------------------------
    def clearance(self, callsign: str, route: Route, target: str,
                  is_departure: bool = False, runway: str = "") -> str:
        """Build a TS3 taxi clearance from a route."""
        if not route.ok:
            return f"{callsign} STANDBY  ({route.reason})"
        via = " ".join(route.taxiways)
        if is_departure:
            head = f"{callsign} RUNWAY {runway}"
        else:
            head = f"{callsign} TAXI TO {target}"
        parts = [head]
        if via:
            parts.append(f"VIA {via}")
        cmd = " ".join(parts)
        # crossings are issued as explicit CROSS RUNWAY clearances (ground owns
        # them only if it owns that runway; otherwise the position manager hands
        # off to whoever does before the cross)
        cross = "; ".join(f"{callsign} CROSS RUNWAY {r}" for r in route.crossings)
        return cmd + (("  | " + cross) if cross else "")

    # ---- helpers -----------------------------------------------------
    def _nid(self, x):
        if isinstance(x, int):
            return x
        return self.g.node_of(x)

    def _edge_between(self, a, b):
        for ei in self.g.adj.get(a, []):
            e = self.g.edges[ei]
            if (e.a == a and e.b == b) or (e.a == b and e.b == a):
                return e
        return None
