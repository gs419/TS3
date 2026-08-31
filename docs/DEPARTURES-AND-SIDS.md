# AI departure controller + real SIDs

Adds a departure controller alongside the arrival one, sharing the same game
state and runway map. Validated on the real KBUR log: it drove VXP165 through
pushback → taxi → line-up → takeoff, and the arrival policy simultaneously held
two arrivals for the same runway because the departure held it.

## Files
- `autocontroller/departure_policy.py` — the departure state machine.
- `autocontroller/departures.py` — SID data model, loader, selection.
- `autocontroller/sids.json` — departure data (**example/placeholder values**).

## Flow (all log-driven, all real command verbs)
```
PILOT "requesting push and start" -> <cs> PUSHBACK APPROVED EXPECT RUNWAY <r>
PILOT "ready to taxi"             -> <cs> RUNWAY <r>            (+ CROSS as needed)
runway free (tick)                -> <cs> RUNWAY <r> LINE UP AND WAIT
runway free (tick)                -> <cs> RUNWAY <r> CLEARED FOR TAKEOFF <SID initial>
POS/ALT line shows airborne       -> handoff (release runway)
```
Runway exclusivity is shared with the arrival policy via
`GameState.runway_reserved_by`, so departures and arrivals sequence on the same
runway automatically (proven in the replay).

## Real departures / SIDs

**Can we pull real airport departures and fly them? Partly — and honestly:**

- **Initial departure instruction (in remit, done):** real towers issue the
  SID's initial turn + initial climb, then hand off. We fold that straight into
  the takeoff clearance using confirmed phrasings:
  `RUNWAY 15 CLEARED FOR TAKEOFF AFTER DEPARTURE TURN LEFT ON COURSE ON
  REACHING ALTITUDE 3000 CONTACT DEPARTURE`.
  `sids.json` holds per-runway `initial_climb_ft` + `turn_on_course`/
  `initial_heading`, with per-destination overrides (`by_dest`).
- **Flying the full multi-leg SID (advanced, opt-in):** the AIR command set
  supports it — `FLY HEADING <hdg>`, `TURN <dir> HEADING <hdg>`,
  `CLIMB TO <alt>` — and `Departure.vector_commands()` emits the ordered legs.
  BUT: (1) the tower is *supposed* to hand off to departure shortly after
  takeoff, so vectoring the whole SID means deliberately holding the aircraft on
  tower frequency; and (2) sequencing legs by fix requires the **live position
  feed** (port `CMD_REQUEST_AIRPLANES`) to know when each leg/fix is reached.
  So this mode needs the port client wired in and the write path confirmed.
  Treat it as an advanced toggle, not the default.

### Getting real SID data
`sids.json` ships **example/placeholder** headings and altitudes so the
mechanism is testable. Replace with real data from public sources:
- **FAA CIFP** (Coded Instrument Flight Procedures), public domain — machine
  readable SID legs, headings, altitudes, fixes.
- **FAA d-TPP** charts — the published SID plates for human cross-check.
Per SID/runway, extract: initial climb, initial heading or "runway heading",
and the first fixes (lat/lon) for `legs[]`. A small converter from CIFP →
`sids.json` is a good follow-up.

Note: to turn a fix's lat/lon into a heading the aircraft can fly, convert via
the airport center (`CMD_REQUEST_AIRPORT._centerlat/_centerlon`) the same way
`port_client.local_to_latlon` does, in reverse — again needing the position
feed for closed-loop leg sequencing.

## Limits / honest notes
- Taxi routing is currently a single `RUNWAY <r>` (game auto-routes). Real
  `VIA <taxiways>` pathfinding wants the airport `roads[]` graph from the port.
- Departure sequencing is "one runway user at a time" + arrival coordination.
  Wake-turbulence spacing (by strip `wc`/weight class) and
  departure/arrival interleaving are the next refinements.
- Everything runs dry-run until the write path is confirmed (one voice-command
  capture). The decision logic is validated on real logs now.
