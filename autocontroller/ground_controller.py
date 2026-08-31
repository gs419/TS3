"""Ground controller ("Bob"): routes aircraft it owns across the taxiways, with
standing guidance plus per-aircraft overrides.

Ties the GroundRouter to a position. Standing guidance encodes the controller's
policy ("always hold short of 24L — that's the human's runway; prefer the outer
taxiways; C is closed today"). Per-call guidance handles one-off instructions
("take this one via D"). Routes from the aircraft's current location (nearest
graph node to its live position) to the assigned target — a handoff hold-short
point, a crossing, or a gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ground_router import GroundRouter, RouteGuidance
from taxi_graph import TaxiGraph


@dataclass
class GroundController:
    name: str
    graph: TaxiGraph
    sender: object
    standing: RouteGuidance = field(default_factory=RouteGuidance)

    def __post_init__(self):
        self.router = GroundRouter(self.graph)

    def _merge(self, override: Optional[RouteGuidance]) -> RouteGuidance:
        if override is None:
            return self.standing
        return RouteGuidance(
            via=override.via or self.standing.via,
            avoid=list(set(self.standing.avoid) | set(override.avoid)),
            prefer=override.prefer or self.standing.prefer,
            prefer_factor=override.prefer_factor,
            runway_cross_penalty=override.runway_cross_penalty or self.standing.runway_cross_penalty,
            hold_short_of=list(set(self.standing.hold_short_of) | set(override.hold_short_of)),
        )

    def reroute_around(self, callsign: str, from_node_or_pos, target: str,
                       blocked: list, guidance: RouteGuidance | None = None) -> str:
        """Dynamic re-routing: taxi to target avoiding newly-blocked taxiways
        (closure, stopped aircraft, congestion)."""
        gd = guidance or RouteGuidance()
        gd = RouteGuidance(via=gd.via, avoid=list(set(gd.avoid) | set(blocked)),
                           prefer=gd.prefer, prefer_factor=gd.prefer_factor,
                           runway_cross_penalty=gd.runway_cross_penalty,
                           hold_short_of=gd.hold_short_of)
        return self.taxi_to(callsign, from_node_or_pos, target, guidance=gd)

    def taxi_to(self, callsign: str, from_node_or_pos, target: str,
                guidance: Optional[RouteGuidance] = None,
                is_departure: bool = False, runway: str = "") -> str:
        """Route an owned aircraft to `target` and issue the clearance.
        `from_node_or_pos` is a node id, a name, or a live pos dict {x,_,z}."""
        start = from_node_or_pos
        if isinstance(from_node_or_pos, dict):
            start = self.graph.nearest_node(from_node_or_pos["x"], from_node_or_pos["z"])
        gd = self._merge(guidance)
        rt = self.router.route(start, target, gd)
        text = self.router.clearance(callsign, rt, target,
                                     is_departure=is_departure, runway=runway)
        self.sender.send(text)
        return text
