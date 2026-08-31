# Dynamic runway lighting — handoff to the airport-builder thread

Purpose: hand the **dynamic runway lighting (RWSL / runway entrance lights)** idea
to the separate airport-builder effort, with everything this thread found so it
doesn't have to rediscover it. Goal: at applicable airports, the hold-short
lights at a taxiway/runway intersection turn RED when the runway is occupied or
an arrival is close.

## Split of concerns
- **This (AI-ATC) thread owns the LOGIC:** *which* lights should be red *when*,
  derived from live traffic. Built and validated — see below.
- **The airport-builder thread owns PLACEMENT/RENDERING:** putting light objects
  at the right spots in the airport and (if possible) making them show state.
  Placement is an airport-build concern, which is why this belongs there.

## What we found about the game's lighting

- **Files (game root):** `light_settings.cfg` (~630 KB — large; per-light
  placement/settings data) and `lights.cfg` (172 bytes — tiny; likely global
  light-type/param definitions). `extwin/` has its own small `lights.cfg`
  (170 bytes). **Contents not parsed by this thread** — the airport-builder
  should inspect these (and the SDK's AirfieldEditor light types) for the light
  schema.
- **Per-airport light geometry** is not in the airport folder's plain files
  (`package.txt`, `databases/`, `instruments/`); it is almost certainly baked
  into the compiled `.airport` binary / SDK scene. So **light placement is a
  build-time artifact** — the airport builder's domain.
- **Runtime controllability — what we can/can't do from outside the game:**
  - The Communication Port protocol (fully decoded, see `PORT-PROTOCOL-DECODED.md`)
    has **no "set light" verb**. `CMD_SET_LAMP_ON` exists but is a UI/record
    lamp, not runway lighting.
  - The command grammar (`commands.csv`) has no lighting command.
  - `light_settings.cfg` is static config, not a live feed.
  - Conclusion: **the game exposes no external hook to recolor lights at
    runtime.** Making real 3D lights change state therefore needs either (a) an
    in-SDK/in-`.airport` feature that supports occupancy-driven or animated light
    states — *unknown, the key question for the builder thread* — or (b) a
    BepInEx/Harmony binary mod that finds the light `GameObject`s (game is
    Mono/Unity; `Assembly-CSharp.dll` decompiles) and drives their emissive color.

## Reusable RWSL logic (this thread — ready to consume)

`autocontroller/rwsl.py` (validated on the real KBUR taxiway graph):
- **Entrance-point discovery:** a runway entrance/hold-short point is a node in
  the airport taxiway graph shared by a **runway-class edge and a taxiway-class
  edge**. On KBUR this yields 16 points on 15/33, 15 on 8/26, etc. The airport
  builder can use this same rule on the `roads[]` graph to know **where to place
  REL lights** — positions come straight out (`Light.pos` = (x, z) game-local
  meters).
- **State rule:** each point is RED when `runway_safety.can_cross` says it's
  unsafe (an arrival's ETA to that point is less than the time to cross + buffer,
  or an aircraft is rolling out / departing on the runway), else GREEN.
- **Reciprocal ends are one physical runway** (traffic on 15 lights 15 AND 33;
  perpendicular 8/26 stays green).
- Validated: an arrival on short final reds all entrance lights on the strip with
  per-point timing, clearing once it lands.

The builder gets, per airport, the **set of light positions**; this thread can
supply the **live red/green state** for each at runtime over a simple feed if the
lights end up externally drivable.

## What the airport-builder thread should decide/do

1. **Investigate the light format** (`light_settings.cfg` / `lights.cfg` / SDK
   AirfieldEditor / `.airport`): are there light *types* for stopbars / runway
   entrance lights, and can any light carry a **dynamic or occupancy-conditional
   state**, or are all lights static-on scenery?
2. **If a dynamic light type exists:** place REL objects at the entrance points
   (rule above) and wire them to the runway-occupancy state — ideally accepting
   the state from this thread's `rwsl.py` feed, or replicating the timing logic
   in-build.
3. **If lights are static only:** two fallbacks —
   - **External RWSL panel** (this thread can build now): a read-only second-
     monitor ground display drawing each hold-short point red/green live. No game
     changes. Delivers the feature visually without touching scenery.
   - **Binary mod**: recolor the in-sim light objects from `rwsl` states.
4. **Make it per-airport opt-in** — real RWSL exists at only some fields, so a
   flag in the airport's config is authentic.

## Pointers
- RWSL logic + entrance-point rule: `autocontroller/rwsl.py`
- Timing/occupancy check: `autocontroller/runway_safety.py`
- Taxiway graph build (+ stitch) from `roads[]`: `autocontroller/taxi_graph.py`
- Live positions: `autocontroller/worldmodel.py` / `port_client.py`
- Port protocol (no light verb): `docs/PORT-PROTOCOL-DECODED.md`
- Broader lighting notes: `docs/DYNAMIC-LIGHTING.md`

## Open questions — RESOLVED by the builder thread (2026)
- **REL/stopbar or animated light type in the SDK/`.airport`?** **No.** The
  `.airport` v16 schema carries no light data (13 scalars + `roads[]`/`knots[]`,
  byte-round-tripped on the real 694 KB KCLE file). All TS3 lights are *derived
  static scenery*: the SDK's `LightGenerator` walks the road network and emits
  meshes under an "Airport Lights" root. No per-light editing, no conditional/
  animated type. So a **native occupancy-driven light is dead** — which our
  decoded port protocol independently confirms (no light verb).
- **Per-airport lights editable/exported?** No — generated from the road
  network at build, not authored per-light.
- **BepInEx mod acceptable?** User's call. It's the only path to real in-sim
  dynamic lights and is a separate Unity-modding project; our side can hand it
  exact fixture positions (Contract A), which is half its work.
- **`light_settings.cfg` — RESOLVED (parsed):** it is a **global rendering /
  color-grading config**, not light placement. Keys: sun rotation, time, cloud
  altitude, contrast/saturation, SSAO, bloom, exposure, hue/tint/temperature,
  chromatic aberration, vignette; a `remap` 8,640-point tone curve (the 630 KB
  bulk); `colorblocks` (33 Unity color-grading gradients, time-of-day keyed);
  `sliderblocks` (14 UI sliders). **Zero** runway/taxiway/REL/stopbar/per-light/
  ICAO references. So **static REL fixtures cannot be added by data either** —
  this file has no per-light records, and `.airport` v16 has no light data;
  lights are procedurally generated by the SDK `LightGenerator`. **Conclusion:
  there is no data-driven light placement anywhere in TS3.** The only path to
  actual in-sim REL lights is a BepInEx mod; otherwise the external RWSL panel
  delivers the feature. Nothing about lighting remains open.

## Agreed integration (see `RWSL-INTERFACE.md`)
Better than this handoff first assumed — the builder already has surveyed hold
positions (`holds()` → real 75 m hold-short points, `saved_gateroads` naming the
exact protected runways, OSM importer placing knots at mapped holding
positions), and a top-down planner that already draws stop bars.

1. **Positions (builder → ATC):** export `<ICAO>.rwsl.json` beside
   `package.txt`; `rwsl.py` consumes it via `RWSL.from_positions_file` —
   surveyed positions + authoritative `runways` protection lists, replacing the
   graph-derived entrances and reciprocal guess.
2. **Live feed (ATC → planner):** `rwsl_feed.serve_rwsl` serves
   `rwsl.feed(world)` at `GET /rwsl`; the planner's "Live RWSL" mode polls it and
   paints bars red/green — the "external panel" with no new UI.
3. **Standalone sim (planner-side):** click a runway → all protecting bars red;
   also validates `saved_gateroads` completeness.

ATC side (this repo) is implemented and validated: `rwsl.py` (Contract A load +
`feed()`), `rwsl_feed.py` (Contract B server), round-trip tested on the real
KBUR graph. Builder side builds 1+2+3 (one rendering path).
