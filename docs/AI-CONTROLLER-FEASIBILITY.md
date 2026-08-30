# Feasibility: an AI auto-controller for Tower! Simulator 3

Question: can an external program observe the game and automatically issue
commands (e.g. clear arrivals to land)? **Yes — a basic auto-controller is
practical today.** The game exposes enough observable state to know when a
plane needs a landing clearance, and it accepts typed text commands, which can
be injected programmatically. No prior community project does this; it would be
a first.

## The loop an auto-controller needs

1. **Observe**: know which aircraft exist, their callsigns, and when one is on
   final for a runway.
2. **Decide**: apply a rule ("arrival on final + runway not in use → clear to
   land").
3. **Act**: deliver `<CALLSIGN> RUNWAY <XX> CLEARED TO LAND` to the game.

All three are covered by evidence gathered from the vendored community sources,
the game's own data files, and official documentation.

## Observing game state (input side)

**Primary channel: `Player.log`** at
`%AppData%\..\LocalLow\FeelThere_*\Tower! Simulator 3\Player.log`.
TS3CallsignHelper (vendored under `community-sources/`) proves this works in
practice — it tails the log live and reconstructs per-aircraft state. The line
vocabulary its parsers rely on:

| Log line prefix / pattern | Meaning |
| --- | --- |
| `GAME START` (+ following block) | session start, airport, config |
| `COMMAND: <CALLSIGN> <command text>` | every command the controller issues, echoed with callsign |
| `SET PlANE: <CALLSIGN>` | plane selection (sic — typo is the game's) |
| `Gen TTS hash ... <CALLSIGN>` then `ADD TTS to Acapela: <text>` | each pilot radio transmission, attributed to a callsign — includes "ON FINAL", readbacks of clearances, etc. |
| `METAR DOWNLOADED: ...` | weather |
| `... => Terminal locked: ...`, `Restarter airplanes /`, `... => CLIENT AP STATE CHANGE` | gate/terminal and lifecycle events |

The pilot-transmission lines are the key signal: TS3CallsignHelper's
`PlaneStateParser` derives states like `IN_RWY_APPROACH` from "ON FINAL" calls
and `IN_RWY_CLR_LAND` from clearance readbacks — exactly the trigger and
confirmation an auto-controller needs. The game's AI TRACON feeds arrivals onto
final and the pilot announces it on tower frequency, so every arrival produces
an observable "on final" event.

Caveats:
- Line formats are undocumented and can change between builds (the `Acapela`
  prefix dates from the older TTS engine; the current MeloTTS-based `tts.exe`
  may have renamed these lines). **Step one on a live machine is a calibration
  pass: play a session, then grep the fresh log to confirm/adjust prefixes.**
- TowerGlance's research (vendored, `docs/research/`) analyzed one log
  conservatively and warns the file mixes diagnostics with events and has only
  partial timestamps. For a basic controller this is acceptable: we react to
  line arrival order, not log timestamps.

**Richer channel (future): the Communication Port.** TowerGlance's
`ts3-data-interface-inventory.md` documents a game-owned loopback TCP listener
(observed on port 12030, selectable in settings) carrying newline-terminated
JSON-like frames, used live by `extwin`, `cpm`, `recog`, and `tts`. The full
live panel state flows through it (extwin renders ADIRS/strips from it). It is
bidirectional and undocumented; reverse-engineering it would give radar-grade
state (positions, speeds) that the log lacks — but it is not needed for a
basic clear-to-land controller.

## Sending commands (output side), ranked by risk

1. **Typed text commands (recommended).** Official docs confirm the game
   "recognizes typed or spoken English commands" with the grammar
   `#airplane1 COMMAND PARAMETERS` — the same grammar as
   `Airports/commands.csv` (`CLEARED_TO_LAND` = `CLEARED TO LAND`, requires
   RUNWAY). The Espanso_TS3 configs (vendored) prove people already drive the
   game by programmatic text expansion into its command box. An
   auto-controller does the same with synthetic keystrokes (SendInput via
   `pyautogui`/`pydirectinput`/AutoHotkey): focus game, type
   `AAL123 RUNWAY 24 CLEARED TO LAND`, press Enter. Zero protocol
   reverse-engineering, uses the game's own parser and its error handling.
   Limitation: needs the game window focused and briefly "steals" the
   keyboard; mitigate by only typing when idle or gating on a hotkey.
2. **Voice-pipeline injection.** `recog.exe` (speech-to-text) serves on
   `127.0.0.1:9000`; `cpm.exe` fuzzy-matches transcript text against
   `commands.csv` (threshold 0.6) and forwards structured commands to the game
   over the Communication Port. Impersonating recog's transcript output to cpm
   would inject commands without touching the keyboard — clean, but requires
   sniffing the recog→cpm message format first (plaintext JSON per
   TowerGlance's captures, so likely easy). Best second step.
3. **Direct Communication Port frames.** Speak the game's own internal JSON to
   the 12030 listener, as extwin/cpm do. Most capable (and the only path that
   could also *read* live radar state), most reverse-engineering, and the
   listener is bidirectional — a malformed write could disturb the game, so
   experiment with saves you don't care about.

## Decision logic for the basic version

State machine per callsign, driven by log events:

- On pilot call containing `ON FINAL` + runway → candidate for clearance.
- Guards before issuing `CLEARED TO LAND`:
  - no other aircraft currently cleared to land/takeoff/lineup on that runway
    (tracked from our own issued commands and `COMMAND:` echoes);
  - a cooldown since the runway was last cleared;
  - callsign not already cleared (readback seen in TTS lines).
- Issue command; confirm via the `COMMAND:` echo line and the pilot readback;
  retry once if no echo within a few seconds.
- Everything else (go-arounds, exits, taxi-in, departures) stays manual at
  first — the human plays ground/clearance, the bot plays a very literal
  "local controller".

Natural extensions once the basic loop works: `EXIT AT`/`TAKE NEXT AVAILABLE
EXIT`, `CONTACT DEPARTURE` after takeoff, lineup/takeoff sequencing, and
eventually an LLM-based policy instead of rules.

## Prototype

`autocontroller/` in this repo contains a Python prototype implementing the
log-tail → state → policy → sender loop with a **dry-run sender by default**
(prints what it would type). See its README for the calibration workflow to
run on the gaming PC. The design intentionally mirrors TS3CallsignHelper's
proven parsing approach.

## Sources

- Vendored: `community-sources/TS3CallsignHelper` (log line formats, state
  machine), `community-sources/TowerGlance/docs/research/*` (Communication
  Port, log characterization), `community-sources/Espanso_TS3` (typed-command
  workflow).
- Game files (OneDrive install): `Airports/commands.csv` grammar,
  `RECOG/config/config.json` (recog on 127.0.0.1:9000, cpm fuzzy matching).
- Official: [Start Guide PDF](https://feelthere.com/wp-content/uploads/2022/12/Start-Guide-Basics-for-Tower-Simulator-3.pdf)
  ("typed or spoken English commands", command grammar, AI TRACON behavior).
