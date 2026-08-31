# Dynamic runway lighting (RWSL / runway entrance lights)

> **Handoff:** light *placement/rendering* is an airport-build concern — see
> `DYNAMIC-LIGHTING-HANDOFF.md` for the spec passed to the airport-builder
> thread. This file covers the logic and delivery options.


Idea: like real **Runway Status Lights (RWSL)** — the red **Runway Entrance
Lights (REL)** at a taxiway/runway hold-short that illuminate when an aircraft is
on the runway or an arrival is close, telling anyone waiting NOT to enter/cross.

## Can we do it? Two honest layers.

### The logic — yes, done (`rwsl.py`)
RWSL is exactly our `runway_safety` check evaluated at each hold-short point.
`rwsl.py`:
- derives every **runway entrance point** from the airport taxiway graph
  (nodes shared by a runway edge and a taxiway edge — 16 on KBUR's 15/33, etc.),
- lights each RED (do-not-enter) or GREEN (clear) from the live WorldModel,
- treats reciprocal ends as one physical runway (traffic on 15 lights 15 **and**
  33; perpendicular 8/26 stays green).

Validated: an arrival on short final to 15 turns all entrance lights on that
strip red with per-point timing (`"DAL10 lands in 8s, crossing needs 45s"`), and
they clear once it lands. This is a correct, live RWSL model right now.

### Painting the lights — where they can show

1. **External RWSL / ground panel (buildable now, read-only).** Drive a
   second-monitor display from `rwsl.compute(world)`: a top-down airport with
   each hold-short point drawn red/green in real time. Safe, needs no write path
   and no game modification — the practical way to get the feature immediately.
   It also doubles as a ground-situational-awareness display (positions from the
   port feed).

2. **The actual in-sim 3D lights (needs a binary mod).** The game's lights come
   from scenery config (`light_settings.cfg` ~630 KB, `lights.cfg`) — static
   definitions, not a runtime-controllable feed. There is **no** "set light
   color" verb in the command grammar, and the port's `CMD_SET_LAMP_ON` is a UI
   lamp, not runway lighting. So recoloring the real 3D lights can't be done from
   data/config alone. It requires a **BepInEx + Harmony mod**: locate the
   runway/taxiway light `GameObject`s (the game is Mono/Unity, so decompiling
   `Assembly-CSharp.dll` to find them is feasible) and drive their emissive
   color from our occupancy data (or compute RWSL inside the mod). This is a
   real but separate Unity-modding project.

## Reality check (matches "at some airports")
Real RWSL is installed at only some major airports — so making it airport-opt-in
is authentic. Our version can enable it per airport in config, and because it's
derived from the taxiway graph it works at any field the port describes.

## Recommended path
- Now: build the **external RWSL panel** (read-only) on top of `rwsl.py` — a
  live red/green hold-short display, no game changes. Highest value, lowest risk.
- Later: if you want the lights *in* the sim view, a BepInEx mod that recolors
  the light objects from the same `rwsl` states. Bigger effort, and the only
  path that touches the game's own rendering.

## Files
- `autocontroller/rwsl.py` — entrance-point discovery + live red/green states
  (validated on the real KBUR graph).
- Uses `runway_safety.py` (timing) + `worldmodel.py` (live positions) +
  `taxi_graph.py` (entrance points).

## Refinements
- Speed-unit calibration (`RunwaySafety.speed_to_mps`) and the airborne `state`
  ints from the write-path capture will sharpen the red/green timing.
- Real hold-short *points* (`holdpoints`) were empty in the capture; entrance
  points are derived from runway∩taxiway intersections instead — populate
  `holdpoints` if a build provides them for exact light positions.
