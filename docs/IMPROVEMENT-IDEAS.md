# AI controller — further improvement ideas

Backlog of enhancements beyond the current controllers, tagged by the data each
needs. Most "decide-side" items are buildable and validatable on data we already
have (log + taxiway graph + port position feed); *acting* on any of them still
waits on the write path.

> **Status (built):** everything below **except section E (Intelligence layer)**
> is now implemented and validated on the decide-side. New modules:
> `runway_selection.py` (A1), `separation.py` (A2), `sequencer.py` (A3),
> `assignment.py` (A6+B9), `ground_conflict.py` (B7,B8,C11), `ground_controller.
> reroute_around` (B10), `scoring_tuner.py` (C12), `deviation.py` (C13),
> `voices.py` (D14–16), `airlines_db.py` (F20), `sid_convert.py` (F19),
> `telemetry.py` (F22), `world_feed.py` (F23), `regression.py` (F21).
> A4 (intersection departures) / A5 (LAHSO) are small policy additions using the
> graph + runway_safety and remain to be wired into the departure/arrival flow.
> **Section E (LLM policy, trainer/debrief) intentionally deferred.**

## A. Controller realism
1. **Wind-based runway selection** — choose the active runway(s) from
   `_winddir`/`_windspeed` (STATUS/AIRPORT), recompute on a wind shift. Today the
   policies use a fixed `default_runway`. Small, high realism, feeds everything.
2. **Wake-turbulence separation** — use the weight class (`wc` on strips/planes)
   to space arrivals and departures behind Heavy/Super. Feeds the sequencer and
   the spacing advisor.
3. **Arrival sequencing / metering** — instead of clearing whoever is on final,
   order arrivals by ETA-to-threshold and insert required spacing, using
   `MAKE SHORT APPROACH` / S-turns / go-around to build the sequence. Biggest
   jump in controller quality.
4. **Intersection departures** — offer a shorter takeoff point from the taxi
   graph when it helps a smaller aircraft / flow.
5. **LAHSO** (land-and-hold-short) — issue `CLEARED TO LAND ... HOLD SHORT`
   using the runway-safety geometry where the field supports it.
6. **Runway/gate-aware assignment** — pick the departure runway and arrival gate
   to minimize taxi (graph distances + `terminals.csv` airline→terminal).

## B. Ground intelligence
7. **Taxi conflict resolution** — detect two aircraft routed onto the same
   segment or head-on and hold one (graph + live positions). Prevents ground
   gridlock; the natural companion to the ground router.
8. **Pushback conflict check** — don't approve a pushback into a taxiing
   aircraft.
9. **Gate assignment by airline** — `terminals.csv` maps airlines to terminals;
   assign arrivals to a correct free gate.
10. **Dynamic re-routing** — reroute around a blockage/closed taxiway on the fly
    (the router's `avoid` guidance already supports it; make it reactive).

## C. Safety / scoring
11. **Ground incursion predictor** — converging taxi paths / runway incursion
    from geometry (extends `runway_safety` onto taxiways).
12. **Scoring-driven self-tuning** — watch `Add Scoring` events; surface which
    mistakes cost points and auto-adjust thresholds (e.g. widen spacing after a
    `RUNWAY_SEPARATION` hit).
13. **Deviation / wrong-runway detection** — compare a plane's movement against
    its clearance; alert on a wrong turn or wrong runway.

## D. Immersion / voice
14. **Per-position voices** — a distinct TTS `voice_id` per controller (Sally vs
    Bob) over the SAY channel, so positions sound different.
15. **Phrasing variety / personality** — vary readbacks and phrasing.
16. **Readback-error trainer** — inject/keep-honest readback checks as a training
    mode.

## E. Intelligence layer
17. **LLM policy** — swap a rule engine for an LLM that reads the world snapshot
    and emits a command validated against `commands.csv` before sending. Best for
    edge cases and natural sequencing. (If pursued, load the `claude-api`
    reference for current model/cost specifics rather than guessing.)
18. **Trainer / examiner & debrief** — grade a session from log + `Add Scoring`
    and explain mistakes; the world model has everything needed.

## F. Tooling / infrastructure
19. **CIFP → sids.json converter** — real SID data (departures ship placeholder
    values today).
20. **Full airline callsign DB** — expand the resolver's small telephony map from
    `airlines.csv`.
21. **Regression harness** — formalize replaying recorded logs/pcaps to test
    every policy on each change (we do this ad-hoc; make it a suite).
22. **Metrics / telemetry** — track handoffs, separations maintained, taxi
    efficiency, score deltas.
23. **General situational display** — a ground/air view beyond RWSL; the world
    model already has the data (dovetails with the planner).

## Dependency summary
- **Buildable + validatable now** (decide-side, existing data): A1–6, B7–10,
  C11–13, F19–23. Mostly need only the log/graph/port data in hand.
- **Needs the write path to *act*:** every controller action — but the
  decide/advise version of each works and can be validated now.
- **Needs new external data:** F19 (FAA CIFP), parts of A/B (nav/airline data).

## Recommended next three
1. **Wind-based runway selection (A1)** — small, high realism, feeds every other
   policy; testable straight from STATUS.
2. **Arrival sequencing + wake separation (A2+A3)** — the biggest quality jump:
   turns "clear whoever's on final" into real flow control; validatable on the
   position feed.
3. **Taxi conflict resolution (B7)** — makes multi-position ground safe at
   volume; reuses the graph + positions already built.
