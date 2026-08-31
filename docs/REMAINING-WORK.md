# What's left

Honest state: the system is a large set of **validated decide-side modules**,
not yet an assembled, acting whole. Remaining work, in priority order.

## 1. The write path — the one hard blocker
Nothing *acts* until the command-injection message is confirmed. One short
voice-command capture settles it (and also the airborne `state` ints + speed
units). See `WRITE-PATH-CAPTURE-GUIDE.md`. Everything else runs dry-run/advisory
until this lands.

## 2. Integration — DONE (core), one piece remaining
The core is assembled and validated end-to-end on the real logs:
- **`CommandArbiter`** (`arbiter.py`) — policies propose; it de-conflicts per
  tick (one command/aircraft, one runway-occupying clearance/runway, cooldowns)
  and forwards winners. ✅
- **Orchestrator** (`orchestrator.py`) — WorldModel (log + optional port) →
  event fan-out to arrival/departure policies + tuner + telemetry → arbiter →
  sender, on a tick loop. Single entrypoint. ✅
- **Config unification** (`config.py`) — one Config; `apply_tunables()` folds
  scoring-tuner learning into live params (proven: tuner adjustments reached the
  config during replay). ✅
- **Still to wire:** the *other* policies (sequencer, spacing, ground
  conflict/router, position manager) into the orchestrator's fan-out + arbiter,
  and **per-position policy scoping** (filter each policy to the aircraft its
  position owns via `mgr.current(cs)`). The arrival+departure+tuner+telemetry
  path is in; the rest are built but not yet mounted on the engine.

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
