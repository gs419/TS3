# Ground router — taxi pathfinding with guidance

Bob (and any ground/ramp position) can now taxi aircraft across the airport by
shortest sensible route, shaped by guidance. Built and validated on the **real
KBUR taxiway graph** from your capture.

## Files
- `taxi_graph.py` — builds a routable graph from the port's `roads[]`.
- `ground_router.py` — Dijkstra with guidance, crossings, handoff routing.
- `ground_controller.py` — a ground position wrapping the router with standing
  guidance.
- `testdata/kbur_airport.json` — real KBUR `roads[]` fixture for tests.

## Building the graph
`TaxiGraph.from_airport(airport)` turns the 95 `roads[]` (each a polyline of
`knots` with positions) into nodes + edges, classifying each edge taxiway /
runway / gate by name. Knots within ~22 m merge into one node.

**Stitching (important).** Taxiways often meet a runway or another taxiway
*mid-segment*, so their junction knots don't coincide — raw, the KBUR graph
fell into **18 disconnected pieces** (18 of 40 gates unreachable).
`.stitch()` snaps each node onto nearby edge segments and splits them,
reconnecting the graph to **2 components (main = 333 nodes, all 40 gates
reachable)**. Always call `TaxiGraph.from_airport(apt).stitch()`.

## Routing + guidance
`GroundRouter.route(start, goal, guidance)` — start/goal may be a gate name,
runway, taxiway, or node id. Returns the taxiway sequence, runway crossings,
and cost. `guidance` (`RouteGuidance`) is how you or a controller shape it:

| Knob | Effect | "Bob, ..." |
| --- | --- | --- |
| `via=[...]` | force the route through these taxiways/points in order | "...take him via C then D" |
| `avoid=[...]` | never use these taxiways | "...C is closed" |
| `prefer=[...]` (`prefer_factor`) | bias toward these | "...use the outer taxiways" |
| `runway_cross_penalty` | cost per runway crossing (high by default) | avoid crossing actives |
| `hold_short_of=[rwy]` | never cross these runways | "...that's my runway" |

All validated on real geometry: forcing a via-point, avoiding a taxiway, and
holding short each demonstrably change the route. Routes never taxi *through*
another aircraft's gate (only the destination gate is traversable).

## Clearance text
`GroundRouter.clearance(callsign, route, target, is_departure, runway)` builds a
TS3 command:
- departure: `SWA1065 RUNWAY 15 VIA G1 G`
- arrival:   `DAL6221 TAXI TO gate_B1 VIA G G1`
- crossings become explicit `... CROSS RUNWAY x` clearances appended.

## Route-to-handoff (ties into multi-position)
`route_to_handoff(start, goal, blocking_runways, guidance)` routes toward the
goal but, if the natural path would cross one of `blocking_runways` (e.g. the
human's 24L), **stops at the hold-short** and reports which runway must be
crossed. That's exactly Bob's job in the Cleveland scenario: taxi to hold short
of your runway, then the PositionManager fires `holding_short:<rwy>` and hands
the aircraft to you to clear the cross. Validated on KBUR (`landed 26 → hold
short via D A S2 S1`).

## Standing vs one-off guidance (`ground_controller.py`)
A `GroundController` carries **standing** guidance (its policy: "hold short of
15, C is closed, prefer G/G1") and merges per-call **overrides** ("take this one
via S2"). `taxi_to(callsign, from_pos_or_node, target, guidance=…)` accepts the
aircraft's live position (snaps to nearest node) and issues the clearance.

## Known limitations / next
- Paths are shortest-cost but not smoothed: a route may name a taxiway twice
  where the path weaves through a junction. A post-pass could collapse these.
- The stitch threshold (38 m) suits KBUR; very large fields may want tuning, and
  one small 21-node island remained (likely an isolated service road). Verify
  `stitch()` connectivity per airport.
- Real hold-short *points* (`holdpoints`) were empty in this capture; crossings
  are detected from runway-class edges instead. Populate holdpoints if a build
  provides them for exact hold-short positions.
- Gate/taxiway names come straight from the airport; spoken clearances would run
  them through the number/phonetic normalization the recognizer uses.
