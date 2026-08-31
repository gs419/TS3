# RWSL interface — contracts between the airport-builder and AI-ATC threads

Canonical spec both threads code against. Two data contracts + one shared
convention. Keep this file in sync across both repos.

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

## Status
- ATC side: implemented and validated — `rwsl.py` loads Contract A, `feed()`
  emits Contract B, `rwsl_feed.py` serves it (round-trip test passes on the real
  KBUR graph).
- Native in-sim dynamic lights: **not possible** — confirmed both sides (no light
  data in `.airport` v16; no light verb in the decoded port protocol). RWSL is
  delivered on the planner screen; changing the actual 3D lights would need a
  separate BepInEx mod (see `DYNAMIC-LIGHTING-HANDOFF.md`).
- Pending: parse `light_settings.cfg` (630 KB, game root) to settle whether
  static REL *fixtures* could be added by data — upload needed.
