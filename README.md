# Tower! Simulator 3 — review, protocol decode & AI ATC toolkit

What began as a review of a Tower! Simulator 3 install (FeelThere's Unity ATC
sim) grew into: a decode of the game's live data interfaces, and an external
**AI air-traffic-control system** that reads the sim, decides like a controller,
and (once the write path is confirmed) issues commands — including multi-position
control where different AI controllers own different runways/areas and hand
aircraft to each other and to you.

Everything here is validated against **real captured data** from the game
(a packet capture + Player.log), not mocks.

## Repository map

| Path | What |
| --- | --- |
| `REVIEW.md` | Review of the OneDrive install (contents, findings). |
| `RESOURCES.md` | Official SDK/docs + community tools survey. |
| `community-sources/` | Vendored open-source community tools (reference). |
| `autocontroller/` | The AI ATC system (Python). |
| `docs/` | Design + decode docs (see index below). |

## How the game exposes data (decoded)

Two channels, both decoded from real captures:

- **`Player.log`** (event stream): `COMMAND:`/`TOWER:` (controller commands with
  callsign), `PILOT:` (spoken pilot calls incl. "on final"), `CREATE SERVER
  AIRPLANE:` (spawns), `Add Scoring: MSG_*` (outcomes). Zero setup.
  → `docs/PLAYER-LOG-FORMAT.md`
- **Communication Port** (loopback TCP, newline-delimited JSON; the game core is
  the server): `CMD_REQUEST_AIRPLANES/STATUS/STRIPS/AIRPORT/FREQS` give
  radar-grade state (positions, headings, speeds, strips) and the airport
  taxiway graph; the TTS channel emits every transmission as text; the recog
  channel is the command-input path. → `docs/PORT-PROTOCOL-DECODED.md`

## Architecture

```
   Player.log ─┐                         ┌─ ArrivalPolicy (clear to land)
               ├─►  WorldModel  ──events──┤─ DeparturePolicy (+ real SIDs)
 Comm Port  ───┘   (fused live state)    ├─ SpacingAdvisor (compression)
 (positions)         │                   ├─ PositionManager (multi-position)
                     │                   ├─ GroundController (taxi routing)
                     │                   └─ RunwaySafety (cross timing)
                     ▼                            │
              one Plane set                       ▼
           (log + geometry)             CommandArbiter (de-conflict)
                                                   │
                                                   ▼
                                        Sender (dry-run | keyboard | port)
```

Each controller is a small policy subscribing to the same event stream; adding
one is a new subscriber, not a rewrite.

## Modules (`autocontroller/`)

| Module | Role |
| --- | --- |
| `gamestate.py` | `Plane`/`GameState` + `LogInterpreter` (calibrated log parser). |
| `callsign_resolver.py` | spoken telephony → ICAO (validated 8/8 on real calls). |
| `worldmodel.py` | fuses log + port position feed into one live picture; runs geometric detectors. |
| `port_client.py` | read-only Communication Port client (handshake + poll + lat/lon). |
| `policy.py` | arrival controller: auto clear-to-land with runway/cooldown guards. |
| `departure_policy.py` + `departures.py` + `sids.json` | departure controller with real-SID initial instructions. |
| `phraseology.py` | "cleared direct X" / "climb via SID" → primitive commands. |
| `positions.py` + `positions.json` + `position_manager.py` | multi-position ownership + handoff fabric (AI↔AI↔human). |
| `taxi_graph.py` | routable taxiway graph from the airport `roads[]` (+ `stitch()`). |
| `ground_router.py` | Dijkstra taxi routing with guidance + path smoothing + handoff routing. |
| `ground_controller.py` | a ground position ("Bob") with standing + per-aircraft guidance. |
| `runway_safety.py` | is-it-safe-to-cross timing check (arrival ETA vs crossing time). |
| `spacing_policy.py` | consumes `compression` events; advises/acts. |
| `senders.py` | command delivery: dry-run (default), keyboard, or port (pending write path). |
| `main.py` | log-tail runner for the arrival/departure loop. |

## Feature status

| Capability | Decide | Act |
| --- | --- | --- |
| Clear-to-land (arrivals) | ✅ validated on real logs | ⏳ write path |
| Departures + real SID initial instr. | ✅ validated | ⏳ write path |
| Cleared-direct / climb-via-SID | ✅ (needs fix DB) | ⏳ write path |
| Compression / spacing | ✅ (needs state-int calibration) | ⏳ write path |
| Multi-position + handoffs | ✅ validated (Cleveland scenario) | ⏳ write path |
| Ground taxi routing + guidance | ✅ validated on real KBUR graph | ⏳ write path |
| Runway cross-timing safety | ✅ validated | ⏳ write path |

**The one blocker to *acting*:** the command write path — a single captured
voice command confirms the injection message. Until then every controller runs
in dry-run/advisory mode (it decides correctly, it just prints instead of
sending). See `docs/WRITE-PATH-CAPTURE-GUIDE.md`.

## Running (on the gaming PC)

Dry-run the arrival/departure loop off the live log:
```
python autocontroller/main.py --log "<...>\Player.log"
```
Live world model with positions (read-only):
```
python autocontroller/port_client.py --port <PORT>     # see the live radar feed
```
Both are safe/read-only. Calibrate once per build with `--replay` (see
`autocontroller/README.md`).

## Docs index
- `PORT-PROTOCOL-DECODED.md` — the Communication Port protocol.
- `PLAYER-LOG-FORMAT.md` — calibrated log line reference.
- `WORLD-MODEL.md` — fusing log + positions.
- `AI-CONTROLLER-FEASIBILITY.md` — the original feasibility case.
- `DEPARTURES-AND-SIDS.md` — departures + real SIDs.
- `CUSTOM-PHRASEOLOGY.md` — direct/climb-via-SID translation.
- `MULTI-POSITION.md` — splitting the airport among controllers.
- `GROUND-ROUTER.md` — taxi pathfinding + guidance.
- `WRITE-PATH-CAPTURE-GUIDE.md` — the one capture that unlocks acting.
- `PORT-12030-FINDINGS.md` — pre-decode investigation (superseded).
- `CONTROLLER-ROADMAP.md` — where this can still go.

## Status & honesty
- Read + decide: built and validated on real data across all features above.
- Act: gated on the write-path capture (one short session).
- This is unofficial, external, read-first tooling for personal use; it uses the
  game's own command grammar and undocumented-but-observed interfaces. Capture
  passively and test any command injection on a throwaway session first.
