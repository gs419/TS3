"""Runway and gate assignment.

- assign_runway: among wind-acceptable runways, pick the one with the shortest
  taxi from the aircraft's position (graph distance).
- assign_gate: for an arrival, pick a free gate in the airline's terminal,
  nearest by taxi. Airline→terminal comes from the airport's terminals.csv
  (loaded via load_terminals).
"""
from __future__ import annotations

import csv
from ground_router import GroundRouter
from runway_selection import rank_runways


def load_terminals(path: str) -> dict:
    """Parse terminals.csv -> {airline_icao: [terminal, ...]}. Column names vary
    by airport; we look for an airline/operator column and a terminal column."""
    out = {}
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            keys = {k.lower(): k for k in row}
            al = next((row[keys[k]] for k in keys if "airline" in k or "operator" in k
                       or k in ("al", "icao")), None)
            tm = next((row[keys[k]] for k in keys if "terminal" in k or "gate" in k
                       or "area" in k), None)
            if al and tm:
                out.setdefault(al.strip().upper(), []).append(tm.strip())
    return out


def assign_runway(graph, from_node, candidate_runways, wind_dir, wind_speed,
                  max_tailwind: float = 5.0):
    """Pick the shortest-taxi runway among wind-acceptable candidates."""
    ok = [w.runway for w in rank_runways(candidate_runways, wind_dir, wind_speed)
          if w.headwind >= -max_tailwind]
    if not ok:
        ok = candidate_runways
    router = GroundRouter(graph)
    best, bestcost = None, 1e18
    for r in ok:
        rt = router.route(from_node, r)
        if rt.ok and rt.cost < bestcost:
            best, bestcost = r, rt.cost
    return best, round(bestcost) if best else None


def assign_gate(graph, from_node, airline_icao, terminals, occupied_gates):
    """Pick a free gate in the airline's terminal(s), nearest by taxi. Falls back
    to any free gate if the airline isn't mapped."""
    wanted = set(terminals.get((airline_icao or "").upper(), []))
    router = GroundRouter(graph)
    cands = []
    for gate in graph.gate_node:
        if gate in occupied_gates:
            continue
        # gate belongs to a terminal if its name contains the terminal token
        in_terminal = (not wanted) or any(t.replace("Terminal", "").strip()
                                          in gate for t in wanted)
        if in_terminal:
            cands.append(gate)
    best, bestcost = None, 1e18
    for gate in cands or list(graph.gate_node):
        if gate in occupied_gates:
            continue
        rt = router.route(from_node, gate)
        if rt.ok and rt.cost < bestcost:
            best, bestcost = gate, rt.cost
    return best, round(bestcost) if best else None
