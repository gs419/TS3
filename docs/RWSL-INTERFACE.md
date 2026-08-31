# RWSL interface — contracts between the airport-builder and AI-ATC threads

Canonical spec both threads code against. Two data contracts + one shared
convention.

## Spec-sync policy (both threads agreed)
This file is **mirrored in both repos** (AI-ATC and airport-builder). Any change
to the interface must be made in **one repo and copied to the other in the same
change** — never let the two copies drift. Bump `version` in Contract A when the
positions-file schema changes; note feed changes here. If the copies ever
disagree, the higher `version` wins and the lower must be updated to match before
either side ships.

**Conformance status:** planner (builder) side reports **fully conformant** as of
its current commit; ATC side implemented + validated (below). An end-to-end
round-trip against a real planner export is ready to run — see "End-to-end check".

## Coordinate convention (shared)
- Game-local metres, the same frame as the port's `roads[]`/`pos` (`x`, `z`).
- Field names on the wire use **`e` (east) = x** and **`n` (north) = z**.
- Origin is the airport reference; lat/lon (if ever needed) via the airport
  `_centerlat`/`_centerlon` as in `port_client.local_to_latlon`.

## Contract A — positions file  (builder → ATC)
The exporter writes `<ICAO>.rwsl.json` beside `package.txt`. One record per
hold-short point, with surveyed position, its taxiway, and the **authoritative**
list of runways that hold protects (from `saved_gateroads`, incl. reciprocals as
appropriate — the ATC side does not re-guess).

```json
{
  "icao": "KCLE",
  "version": 1,
  "holds": [
    { "e": 125.0, "n": -306.0, "taxiway": "C", "runways": ["24L", "6R"] },
    { "e": -940.2, "n": 700.0, "taxiway": "P", "runways": ["24R", "6L"] }
  ]
}
```
- `runways`: every runway this stop bar guards. A hold is RED when **any** listed
  runway is hot. This replaces the ATC side's graph-derived entrances and its
  reciprocal guess — surveyed positions + real protection lists.
- Consumed by `RWSL.from_positions_file(path, graph=…)`.

## Contract B — live feed  (ATC → planner)
The ATC side runs a localhost HTTP server (`rwsl_feed.serve_rwsl`). The planner's
"Live RWSL" mode polls it (suggested 2–4 Hz) and paints each stop bar.

```
GET http://127.0.0.1:8770/rwsl
->
[
  { "e": 125.0, "n": -306.0, "state": "RED",   "reason": "HOLD: DAL6221 lands in 8s, crossing needs 45s" },
  { "e": -940.2, "n": 700.0, "state": "GREEN", "reason": "24R/6L clear" }
]
```
- `state`: `"RED"` (do not enter) | `"GREEN"` (clear).
- `reason`: human-readable, for tooltips/logs (not machine-parsed).
- Records are matched to the planner's bars by `(e, n)` — the same positions the
  planner exported in Contract A, so they line up exactly.
- Localhost only; `Access-Control-Allow-Origin: *` is set for a local webview.
- Port is configurable; default `8770`.

## Contract D — traffic feed  (ATC → planner)  [proposed]
The planner already polls a `/traffic` feed to draw aircraft. The ATC side
serves it via `world_feed.serve_world` at `GET /traffic` (alias `/world`):

```
GET http://127.0.0.1:8771/traffic
->
{ "center": [lat, lon],
  "planes": [
    { "callsign": "DAL6221", "e": -950.0, "n": -400.0, "lat": .., "lon": ..,
      "heading": 68.0, "speed": 70.0, "alt": 600.0,
      "phase": "ON_FINAL", "runway": "24L", "target_runway": "24L" }
  ] }
```
- `e`/`n` game-local metres (same frame as Contract A), lat/lon for convenience.
- **Schema is proposed** — planner confirms field names it needs; adjust here in
  sync. Implemented on the ATC side (`world_feed.py`), served on `/traffic` now.

## Contract C — standalone simulation (planner-side, no feed)
For plan-time preview and to verify `saved_gateroads` completeness: click a
runway in the planner → light every bar whose `runways` include it (and its
reciprocal), lead-ons dark. Pure builder-side; uses only Contract A data. If a
bar that should protect the runway stays dark, its `runways` list is incomplete.

## Division of work (agreed)
- **Builder side:** the export (Contract A), the planner rendering, "Live RWSL"
  mode (polls Contract B), and standalone sim (Contract C). One rendering path.
- **ATC side (this repo):** consume Contract A (`RWSL.from_positions_file`),
  serve Contract B (`rwsl_feed.serve_rwsl` over `rwsl.feed(world)`), keep the
  occupancy/timing logic (`runway_safety`) current.

## End-to-end check (when a real planner export lands)
```
python -c "from rwsl import RWSL; ok,errs,s=RWSL.validate_positions('KCLE.rwsl.json'); print(ok, s, errs)"
```
`RWSL.validate_positions` conformance-checks an export against Contract A
(numeric e/n, non-empty string `runways`, string `taxiway`). If it passes,
`RWSL.from_positions_file(...)` + `rwsl_feed.serve_rwsl(...)` will serve a live
feed the planner can poll — the full round-trip. Drop a real `<ICAO>.rwsl.json`
here and it's one command.

## Status
- ATC side: implemented and validated — `rwsl.py` loads Contract A, `feed()`
  emits Contract B, `rwsl_feed.py` serves it. **End-to-end proven on the real
  planner export** `KCLE2030.rwsl.json` (committed at
  `autocontroller/testdata/`): Contract A validates (36 holds, 6 runways); an
  arrival to 24L reds exactly the 15 holds protecting 6R/24L and leaves the
  6L/24R and 10/28 holds green; `GET /rwsl` returns 36 records matching compute.
- Contract D (`/traffic`): implemented on the ATC side (`world_feed.py`); schema
  proposed, planner to confirm field names.
- Native in-sim dynamic lights: **not possible** — confirmed both sides (no light
  data in `.airport` v16; no light verb in the decoded port protocol). RWSL is
  delivered on the planner screen; changing the actual 3D lights would need a
  separate BepInEx mod (see `DYNAMIC-LIGHTING-HANDOFF.md`).
- **Lighting — closed (both threads, independent parses agree).**
  `light_settings.cfg` is environment/grading only — the 8,640-point daily curve
  is the bulk, `AirportsLight24H` is the one global lights dial, no per-light
  data. `.airport` v16 carries no light data; lights are procedurally generated
  by the SDK `LightGenerator`. There is no data-driven light placement anywhere,
  so static REL fixtures can't be added by data either. RWSL is a planner-screen
  feature (or a BepInEx mod for in-sim lights). Nothing about lighting remains
  open.
