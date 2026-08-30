# Player.log format — current build (calibrated)

Calibrated against real logs from this install (`Player.log` + `Player-prev.log`,
KBUR/KATL sessions, build v1.5.x with the MeloTTS voice stack). This **replaces
the older TS3CallsignHelper line vocabulary** (the `ADD TTS to Acapela:` era) —
the current build uses clearer, prefixed lines.

Location: `%AppData%\..\LocalLow\FeelThere_*\Tower! Simulator 3\Player.log`
(`Player-prev.log` = previous session). ~1.9k–7k lines/session, mixing Unity
diagnostics with game events. React to line arrival order, not timestamps
(only ~20% of lines are timestamped).

## Event lines that matter

| Prefix | Example | Use |
| --- | --- | --- |
| `CREATE SERVER AIRPLANE: <ICAO>` | `CREATE SERVER AIRPLANE: VXP165` | plane spawned → add to roster |
| `SET PlANE: <ICAO>` | `SET PlANE: VXP165` | currently selected plane (sic: "PlANE") |
| `COMMAND: <ICAO> <text>` | `COMMAND: DAL6221 RUNWAY 26R CLEARED TO LAND` | **controller command, with callsign + uppercase text + numeric runway** — the reliable command signal |
| `TOWER: <ICAO> <text>.` | `TOWER: VXP165 RUNWAY 15 VIA A.` | tower TTS of the same command (redundant with COMMAND) |
| `Real commands: <text>` | `Real commands: PUSHBACK APPROVED EXPECT RUNWAY 15` | parsed command, no callsign (applies to selected plane) |
| `PILOT: <spoken text>` | `PILOT: Burbank tower, southwest ten sixty-five on final one five.` | **pilot transmission, SPOKEN form** — carries the on-final trigger |
| `FEELTHERE TTS SAY [voice]: <text>` | `FEELTHERE TTS SAY [7]: pushback approved ...` | text sent to TTS (spoken form) |
| `ADD TTS: [id / PRIORITY]: <text>` | `ADD TTS: [11 / HIGH]: pushback approved ...` | queued TTS with priority |
| `TTS recv: {json}` | `TTS recv: {"result": {...}}` | TTS module reply (mirrors the port's TTS channel) |
| `Add Scoring: MSG_*` | `Add Scoring: MSG_LANDING_SUCCESSFUL` | **outcome/scoring events** (see scoring.csv) — landings, takeoffs, crashes, separation, forgot-departure, unhandled |
| `RUNWAY CROSS ERROR: X x Y` | `RUNWAY CROSS ERROR: 8 x 26` | runway conflict geometry |
| `Local traffic found: <ICAO>` | `Local traffic found: N915KB` | GA/local traffic |
| `Read CSV ...` | — | data-file loads (startup) |

## The spoken vs. ICAO wrinkle (important)

`COMMAND:`/`TOWER:` use **ICAO codes + numeric runways** (`DAL6221`, `26R`).
`PILOT:` uses **spoken telephony** (`delta sixty-two twenty-one`, `two six
right`). To act on a pilot's on-final call you must map spoken → ICAO.

`autocontroller/callsign_resolver.py` does this and is **validated 8/8** against
the real on-final calls in these logs:

| Spoken (PILOT line) | Resolved |
| --- | --- |
| southwest ten sixty-five / one five | SWA1065 / 15 |
| sky west fifty-nine fourty-three / two seven left | SKW5943 / 27L |
| delta sixty-nine zero five heavy / two seven left | DAL6905 / 27L |
| delta thirty seventy-three / two six right | DAL3073 / 26R |

Method: airline telephony → ICAO prefix (seeded map, extend from
`airlines.csv`), spoken flight-number groups → digits (handles hyphens,
`zero five`→`05`, teens, tens+unit), then disambiguate against the live roster
built from `CREATE SERVER AIRPLANE`. "heavy"/"super" suffixes are stripped.

## On-final trigger

`PILOT: [<airport> tower,] <spoken callsign> on final <spoken runway>.`
This is the arrival's request for landing clearance — the auto-controller's
cue to issue `CLEARED TO LAND`. Confirmation of delivery comes from the
matching `COMMAND: <ICAO> RUNWAY <n> CLEARED TO LAND` echo.

## Validation

`gamestate.py` (calibrated to these prefixes) + `policy.py` replayed over both
real logs: tracked 52 planes, resolved all 8 spoken on-final calls, issued 4
`CLEARED TO LAND` commands, and correctly **withheld 2** whose runway was
already occupied by another arrival — the runway-occupancy guard working on
real data. All 13 scoring event types were captured.

## Notes / gotchas

- `SET PlANE` is misspelled in the game — match it literally.
- `Add Scoring` is a ready-made feedback channel for a trainer/scorer or for
  the safety-net mode (watch for `MSG_CRASH`, `MSG_RUNWAY_SEPARATION`,
  `MSG_FORGOT_DEPARTURE`).
- The same TTS text visible here also flows over the Communication Port
  (`TTS recv:` mirrors the port's TTS channel), so log and port agree — the
  port additionally gives positions the log lacks.
