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
| `rwsl.py` + `rwsl_feed.py` | runway status lights (red/green hold-shorts) + localhost feed. |
| `runway_selection.py` | wind-based active-runway selection. |
| `separation.py` | wake-turbulence separation minima by weight class. |
| `sequencer.py` | arrival sequencing/metering with wake spacing. |
| `assignment.py` | shortest-taxi runway + airline-terminal gate assignment. |
| `ground_conflict.py` | taxi conflicts, head-ons, pushback, runway incursions. |
| `scoring_tuner.py` | self-tunes params from `Add Scoring` outcomes. |
| `deviation.py` | wrong-runway / off-route detection. |
| `voices.py` | per-position TTS voices, phrasing variety, readback checks. |
| `airlines_db.py` / `sid_convert.py` | airline callsign DB / SID data converter. |
| `telemetry.py` / `world_feed.py` / `regression.py` | metrics / situational feed / replay test harness. |
| `spacing_policy.py` | consumes `compression` events; advises/acts. |
| `senders.py` | command delivery: dry-run (default), keyboard, or port (pending write path). |
| `arbiter.py` | CommandArbiter — de-conflicts every policy's proposed commands per tick. |
| `config.py` | unified runtime config; folds in scoring-tuner learning. |
| `orchestrator.py` | the assembled engine: WorldModel → policies → arbiter → sender, on a tick loop; loads the position map and runs the handoff chain. |
| `main.py` | log-tail runner for the single-AI arrival loop (dry-run / keyboard). |
| `live.py` | **the live runner**: multi-position engine against the running game — tails the log, polls the port, sends via the port write path. |
| `position_editor.py` | **local GUI** to pick an airport and designate which AI/human controls each position and runway (edits `positions.json`). |

## Feature status

| Capability | Decide | Act |
| --- | --- | --- |
| Clear-to-land (arrivals) | ✅ validated on real logs (sequencing fix: runway released off the landing-state machine) | ✅ **live — confirmed in-game** via `live.py` |
| Departures + real SID initial instr. | ✅ validated | ✅ live via `live.py` |
| Cleared-direct / climb-via-SID | ✅ (needs fix DB) | ✅ live |
| Compression / spacing | ✅ (state enum calibrated) | ✅ live |
| Multi-position + handoffs | ✅ validated on the real KBUR log (clear → CONTACT GROUND → TAXI TO RAMP → complete; human runway left alone) | ✅ live via `live.py` + `positions.json` / GUI |
| Ground taxi routing + guidance | ✅ validated on real KBUR graph | ⏳ live ground uses a safe `TAXI TO RAMP`; routed taxi not yet in the live loop |
| Runway cross-timing safety | ✅ validated | ✅ live |

**Acting works — confirmed in-game.** The write path is the Communication
Port: open a recognition session with `CMD_SET_PTT_STATE "true"` plus the
`btnRecognize` button signal (that combination executed every time), stream the
command text with `CMD_SET_CMD_TEXT` while it is held (~1.5 s), release with
`"false"` — the game parses, executes and reads it back exactly like a spoken
command (`docs/PORT-PROTOCOL-DECODED.md`). `live.py` sends through it via
`senders.PortCommandSender`; `tools/probe_write_path.py` is what confirmed it.

## Running (on the gaming PC)

1. **Designate who controls what** — open the GUI, pick the airport, assign
   each position to an AI name or *Human*, and pick the owner of every runway:
   ```
   python autocontroller/position_editor.py          # opens http://127.0.0.1:8765
   ```
   (It edits `autocontroller/positions.json`; you can also edit that by hand.)
2. **Run live** against the game (a session must be running; port is the
   *Communication Port* in the game's settings):
   ```
   python autocontroller/live.py --log "<...>\Player.log" --icao KBUR --port 12020
   python autocontroller/live.py --log "<...>\Player.log" --icao KBUR --dry-run   # print only
   ```
   Runways owned by a *Human* position are left entirely to you; the AI only
   clears its own runways and hands landed traffic to the AI ground position
   (`CONTACT GROUND` → `TAXI TO RAMP`).

Read-only helpers, always safe:
```
python autocontroller/main.py --log "<...>\Player.log"     # single-AI dry-run loop
python autocontroller/port_client.py --port <PORT>         # live radar feed
```

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
- Act: **confirmed in-game** — the port write path executes commands with full readback.
- This is unofficial, external, read-first tooling for personal use; it uses the
  game's own command grammar and undocumented-but-observed interfaces. Capture
  passively and test any command injection on a throwaway session first.
