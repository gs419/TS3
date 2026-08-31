# What's left

Honest state: the system is a large set of **validated decide-side modules**,
not yet an assembled, acting whole. Remaining work, in priority order.

## 1. The write path — the one hard blocker
Nothing *acts* until the command-injection message is confirmed. One short
voice-command capture settles it (and also the airborne `state` ints + speed
units). See `WRITE-PATH-CAPTURE-GUIDE.md`. Everything else runs dry-run/advisory
until this lands.

## 2. Integration — the biggest real engineering gap
~20 modules are built and each validated in isolation, but they are **not wired
into one runtime**. Needed:
- **`CommandArbiter`** — collect proposed commands from all policies each tick
  (arrival, departure, sequencer, spacing, ground router, conflict, positions),
  de-conflict them (never two clearances on one runway/aircraft per tick), apply
  cooldowns, and hand the winner to the sender. The README diagram assumes this;
  it doesn't exist yet.
- **Orchestrator / launcher** — one entrypoint that starts the WorldModel +
  PortClient + log tail + all policies + the RWSL/world feeds, on a tick loop.
  `main.py` today only runs the arrival/departure log loop.
- **Config unification** — every module has its own thresholds; there's no
  single config, and `scoring_tuner`'s `Tunables` output isn't consumed by
  anything yet. Wire tuner → policy params, and expose one config file.
- **Per-position policy scoping** — filter each policy to the aircraft its
  position owns (one-line `mgr.current(cs)` gate), so the multi-position layer
  actually drives the per-position controllers.

## 3. Live calibration — user-only, needs the running game
Everything is validated on captured/synthetic data, never against the live sim:
- `RunwaySafety.speed_to_mps` (AIRPLANES `spd` units) — calibrate from one
  airborne pass.
- Airborne `state` ints for approach/on-final/rollout — from the same capture.
- End-to-end behaviour once the write path is in — start on an easy field
  (KBUR, one runway) in copilot mode before letting it run.

## 4. Real data to gather (replaces synthetic/placeholders)
- **SIDs:** real FAA CIFP → `sid_convert` (ships placeholder `sids.json`).
- **airlines.csv / terminals.csv:** load the actual per-airport files
  (`airlines_db`/`assignment` currently tested on synthetic tables).
- **positions.json:** real per-airport position splits + frequencies (KCLE/KBUR
  examples are illustrative).
- **RWSL positions:** the planner's real `<ICAO>.rwsl.json` export (validator +
  feed are ready).
- **light_settings.cfg:** parse to settle static REL fixtures (pending upload).

## 5. Remaining small features
- A4 intersection departures, A5 LAHSO — small policy additions using the graph
  + runway_safety.
- Wire A1 (wind runway selection) into the departure/arrival policies (module
  exists; policies still use a fixed default runway).

## 6. Robustness / polish
- Taxi graph: one small disconnected island remained after `stitch()`; verify
  connectivity per airport. Route smoothing handles weaves but very large fields
  may need tuning.
- Multi-runway / dependent-runway edge cases in the sequencer and runway_safety.
- Committed test fixtures + a CI run of `regression.py` so changes are guarded
  automatically (harness exists; no fixtures committed).

## 7. Deferred by choice
- Section E (LLM policy, trainer/debrief) — intentionally on hold.
- In-sim dynamic lights (BepInEx mod) — separate Unity project; external RWSL
  panel delivers the feature without it.

## Suggested order
1. **CommandArbiter + orchestrator + config** (#2) — turns the parts into a
   coherent engine; fully doable now, no game needed. Biggest value.
2. **Write-path capture** (#1) — unlocks acting.
3. **Live calibration** (#3) once #1 is in.
4. Real data (#4) and small features (#5) as they come.
