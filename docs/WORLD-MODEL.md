# World model — fusing the log event stream and the live position feed

`autocontroller/worldmodel.py` is the layer the geometric features need. It
keeps one set of `Plane` objects, updated from **both** sources, keyed by
callsign:

- **Player.log** (via `LogInterpreter`) → phase, clearances, roster, scoring,
  departure intents. Event-driven, zero setup.
- **Communication Port** (via `port_client.py`) → live `pos`, `heading`,
  `speed`, `alt`, and derived `latlon`, refreshed each poll. This is what the
  log cannot give.

Both write the same `Plane` (now carrying geometry fields), so a policy sees one
fused picture and never cares which source filled a field.

## What it unlocks (all validated on real captured data / synthetic geometry)

- **Live positions:** replaying the real captured `CMD_REQUEST_AIRPLANES`
  snapshots, the model tracked all 18 aircraft with correct headings and
  lat/lon (KBUR).
- **`cleared direct <FIX>`:** `WorldModel.bearing_to_latlon(plane, fix)` returns
  the magnetic heading from the plane's live position to a fix — verified
  (NE fix, 12°E variation → 028°; cardinals N/E/S/W → 360/090/180/270; local↔
  lat/lon round-trips to <1 m). Fixes come from nav data (FAA CIFP).
- **Compression/spacing:** `_detect_compression` groups airborne arrivals by
  target runway, orders them in-trail, and emits a `compression` event on the
  trailing aircraft when the gap is below `min_spacing_nm` **and shrinking**.
  Verified on a synthetic pair: silent at 5 nm and at first sight, fires at
  2.0 nm closing. `spacing_policy.SpacingAdvisor` consumes it (advise, or
  auto go-around).
- **Foundation for go-around revectoring:** the live `pos`/`heading` let a
  revector state machine time each turn relative to the runway — the remaining
  build.

## Bug found & fixed by this work

Wiring real geometry surfaced a unit error in `phraseology.latlon_to_local`: it
applied `math.radians()` to the longitude delta before multiplying by
meters-per-degree, making east/west distances ~57× too small. Fixed to
`(lon-lon0) * 111320 * cos(lat0)`; now the inverse of `local_to_latlon` exactly
(round-trip < 1 m).

## Running it live

```
from worldmodel import WorldModel, WorldRunner
from port_client import PortClient
wm = WorldModel(on_event=dispatch)          # dispatch fans out to policies
pc = PortClient(port=12020); pc.connect()
WorldRunner(wm, pc, log_path=r"...\Player.log", poll_hz=2).run()
```
`WorldRunner` tails the log and polls the port in one loop, priming the airport
center (for lat/lon) from `CMD_REQUEST_AIRPORT`. Set `wm.magvar_deg` for the
field (KBUR ≈ +12°E) so headings are magnetic.

## Still required to *act* on any of this
- **Write path** (one voice-command capture) — until then, geometric policies
  advise/dry-run just like the log-only ones.
- **Nav-data fix DB** for `cleared direct`.
- **State-enum calibration:** `_airborne()` currently keys off altitude/speed;
  the exact AIRPLANES `state` ints for approach/on-final want one live capture
  with an airborne arrival (the pcap we have was all ground traffic) to refine.

## Architecture
`WorldModel` (log + port) → `on_event` fan-out → policies (`AutoTowerPolicy`,
`DeparturePolicy`, `SpacingAdvisor`, future `RevectorPolicy`) → `CommandArbiter`
(de-conflict) → `Sender`. Adding a controller is a new subscriber, not a rewrite.
