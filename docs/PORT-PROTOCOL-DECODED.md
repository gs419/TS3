# TS3 Communication Port — protocol DECODED

Decoded from a live packet capture (`TS32.pcapng`, KBUR session, 114k packets).
This supersedes the "unknown schema" status in `PORT-12030-FINDINGS.md`: the
protocol is now understood. **As far as this survey found, this is the first
public decode of the channel.**

Sanitized real message samples are in `port12020-samples/`.

## TL;DR

- The port is **settings-selectable**: TowerGlance saw 12030; **this capture
  used 12020**. Don't hardcode it — read it from game settings or scan.
- It is a **newline-delimited JSON message bus**. The **game core is the TCP
  server**; helper modules connect as **clients**. (The core identifies itself
  as `"core": "Tower Simulator 4"` — an internal/next name.)
- Three client roles were captured, each its own connection:
  1. **TTS** — core sends `SAY` commands (the text of every radio
     transmission); module returns synthesized audio.
  2. **recog** — core pushes the recognition **lexicon**; module streams back
     recognized speech (`CMD_RECOG_UPDATE`). This is the **command-input path**.
  3. **Data/DBRITE-control client** — polls live **airplanes / status / strips
     / airport / freqs** and issues **control writes** (PTT, runway,
     separation, lamp). This is the **radar-grade read** channel.
- Everything is plaintext. Reading live aircraft state is straightforward;
  full positions, headings, speeds, states, and flight strips are all exposed.

## Framing & handshake

- Transport: TCP on the Communication Port, loopback (`127.0.0.1`).
- Framing: one JSON object per line. Server→client lines are `\r\n`-terminated;
  client→server lines are `\n`-terminated. Parse by splitting on newline.
- On connect, a client sends a **greeting**; the core replies with a
  **welcome** carrying a security check:
  ```json
  // client -> core
  {"greeting":{"name":"TTS","author":"FeelThere Inc.","type":"TTS","version":"v0.2025.349.1000","description":"Text-to-speech module","security":"0"}}
  // core -> client
  {"welcome":{"security check":"fail/pass","core":"Tower Simulator 4","author":"FeelThere Inc.","version":"v0.0.1.1","description":"core description"}}
  ```
  (The literal string `"fail/pass"` is what the core sent — the security gate
  appears permissive/unenforced in this build. Treat as unverified.)

## Message envelopes

Two envelope styles appear:

**Control/request style** (data client, recog):
```json
{"cmd":"CMD_REQUEST_AIRPLANES","value":"<stringified-JSON-or-empty>","id":11,"flags":0,"func":""}
```
- `cmd`: verb (see tables). `value`: a **string** that itself contains JSON
  (double-encoded) for data-bearing messages, or `""` for a bare request.
- `id`: client request counter. `flags`/`func`: mostly `0`/`""`/`null`.
- Request/response: the client sends `{cmd,value:""}`; the core replies with
  the **same `cmd`** and a populated `value`.

**Typed-params style** (TTS):
```json
{"cmd":{"type":"SAY","params":{"voice_id":7,"quality":0,"speed":1.1,"text":"pushback approved expect runway one five .  avelo one sixty-five . "}}}
```

## Verb reference

### Data client → core (requests & control)
| Verb | Meaning |
| --- | --- |
| `CMD_REQUEST_FREQS` | list of ATC frequencies (once) |
| `CMD_REQUEST_UICFG` | paths to strip/adirs/dbright/weather CSVs (once) |
| `CMD_REQUEST_AIRPORT` | airport metadata + geometry (once) |
| `CMD_REQUEST_STATUS` | game status snapshot (polled ~ many/s) |
| `CMD_REQUEST_AIRPLANES` | all aircraft with full state (polled) |
| `CMD_REQUEST_STRIPS` | flight strips (polled) |
| `CMD_SET_PTT_STATE` | `"true"`/`"false"` — push-to-talk state |
| `CMD_UPDATE_RUNWAY` | set active runway config (value = runway object) |
| `CMD_SET_SEPARATION` | TRACON separation distance (meters, as string) |
| `CMD_SET_LAMP_ON` | `"True"`/`"False"` UI lamp |

### core → recog / recog → core
| Verb | Direction | Meaning |
| --- | --- | --- |
| `CMD_RECOG_HELPER` | core→recog | full recognition **lexicon** (see below) |
| `CMD_RECOG_UPDATE` | recog→core | recognized-speech update; `flags:1` = interim. `value` carries recognized text (empty in this capture — no committed voice command was captured). |

The `CMD_RECOG_HELPER` lexicon `value` (double-encoded JSON) has keys:
`numbers, runways, taxiways, bignumbers, airplanes, freqs, taxivia_alts,
targets, directions, takeoff_alts, cardinals, patternpos, commands, language`.
`airplanes` lists the current callsigns as spoken forms; `commands` is the
command grammar. The core rebuilds and repushes this as traffic changes — it is
effectively a live "what can be said right now" dictionary.

### core → TTS / TTS → core
| Message | Direction | Meaning |
| --- | --- | --- |
| `{"cmd":{"type":"SAY","params":{voice_id,quality,speed,text}}}` | core→TTS | speak this transmission. **`text` is the plain-English radio call** (pilot requests, controller read-backs). |
| `{"greeting":...}` / `{"status":...}` / `{"synthesis_info":...}` | TTS→core | module handshake, RUNNING/IDLE/PROCESSING, model config (MeloTTS `Feelthere-Custom-Voices`, EN, cpu). |
| `{"result":{"type":"SAY","params":{message_id,voice_id,speed,waveform}}}` | TTS→core | synthesized audio; `waveform` is base64 PCM. |

## Key data shapes

### CMD_REQUEST_AIRPLANES → `value.planes[]` (radar-grade)
Per-aircraft top-level fields observed:
```
name     callsign (e.g. "VXP165")
state    int lifecycle enum (values seen: 2, 8, 12, 14 — all ground states this capture)
cat      aircraft category   wc  weight class
pos  {x,y,z}   local metric position (meters); y = altitude (0 on ground)
tstr {x,y,z}   target/smoothed position
rot  {x,y,z}   orientation; rot.y = heading (deg)
trgrot   target heading      trgrw  target runway id
spd      speed               lv     ? (level/vertical)
own      owning frequency (e.g. 123.9)      terminal  gate id
flags    bitfield            netidx  stable per-plane index
route[]  waypoints           metar, act, sndst, tofft, pt_lt, lt
tbl {..} flight-plan block: call, from, to, airline, pl_icao, pl_iata,
         regcode, prefer_runways, local, ga, entry_alt, ...
```
Convert `pos` to lat/lon using `CMD_REQUEST_AIRPORT`'s `_centerlat` /
`_centerlon` (local ENU: x≈east, z≈north, meters).

### CMD_REQUEST_STATUS → `value`
```
game_state ("GAME"), icao, loading, pause, speed, daytime,
selected_plane, tracon_separation, controllerpos, metar_infocode,
rec_btn, rec_state, lamp_on, _winddir, _windspeed, ...
```

### CMD_REQUEST_STRIPS → `value.strips[]`
Electronic flight strips: `name, type (B73W), from, to, wc, cs (AVELO),
own (freq), dep (bool), rnd, arn, utc, fllv, netidx, rwcnt, ...` — matches the
striplook.csv columns.

### CMD_REQUEST_AIRPORT → `value`
`icao, name, _centerlat, _centerlon, _winddir, _windforce, _alt, _gmtoffset,
callsign_tower, callsign_ground, roads[]`, runway geometry, etc.

## What this unlocks

- **Read (confirmed, easy & safe):** connect, handshake as a data client, poll
  `CMD_REQUEST_AIRPLANES`/`STATUS`/`STRIPS`. Full live radar picture —
  positions, headings, speeds, states, strips, frequencies — far beyond
  `Player.log`. A working read-only client is in
  `../autocontroller/port_client.py`.
- **Read speech (confirmed):** subscribe as (or sniff) the TTS channel to get
  every transmission as text the instant it's spoken — a perfect, immediate
  event feed (no log-format guessing).
- **Write / command injection — DECODED (second capture, KBUR, port 12020):**
  the recognizer pushes the command into the game's command box via
  **`CMD_SET_CMD_TEXT`**:
  ```json
  {"cmd":"CMD_SET_CMD_TEXT","value":"ups87 pushback approved expect runway 15","flags":1,"func":null}
  ```
  The `value` is the phraseology the game parses: **callsign + command words**
  (lowercase, e.g. `ups87 pushback approved expect runway 15`). It streams as
  recognition progresses (word-by-word, `flags:1`); the TTS then reads the
  command back, confirming execution ("negative, unknown command" is the failure
  reply).

  **What the working voice session actually sends (capture report):** the
  recognizer module does NOT send one text message. It **streams the growing
  hypothesis, ~10×/s for several seconds while the button is held** —
  `ups87 pushback approved` ×32 → `…expect` ×12 → `…expect runway` ×10 →
  `…runway 1` ×6 → `…runway 15` ×20 — all `flags:1`, no `flags:0`, and no
  port-side PTT: the module reports its own button as
  `CMD_RECOG_UPDATE {"btnRecognize":true|false,"airplanes":""}` (`flags:0`,
  also sent as a heartbeat). `CMD_SET_PTT_STATE` in the first capture came from
  the DATA/DBRITE client (same `id` counter as its `CMD_REQUEST_STATUS`).

  **First live test (KBUR, this build) — what the game logs:**
  - `CMD_SET_PTT_STATE "true"` over the port → `recog_init: True / True / 0`
    (the radio squelch): **port PTT does open a recognition session.**
  - ONE `CMD_SET_CMD_TEXT` sent 50 ms after the press, then `"false"` 50 ms
    later → `COMMAND: ` (**empty**) → `recog_stop` → `recog_cb_end`. The release
    executed, but the box was empty — a single text message right after the
    press is not picked up.
  - text alone with no session → nothing at all.
  - For comparison, the in-game recognizer path logs per hypothesis
    `ALT: 94%: <spoken>` / `REC: <spoken>` / `->: <normalized>` /
    `FINAL: "<normalized>"` / `recog_cb_hypo`, and executes `COMMAND: …` as soon
    as the normalized text is a complete command (before `recog_stop`).

  So the injection must look like the module: **open a session, hold it
  ~1–2 s while streaming the text repeatedly, then release.**
  `senders.PortCommandSender` now does exactly that, with the session signal
  selectable (`ptt_mode`: `ptt` = `CMD_SET_PTT_STATE`, `btn` =
  `btnRecognize`, `both`, `none`), and `tools/probe_write_path.py` tries the
  four variants against the running game with hard evidence (STATUS `cmdtxt` /
  `rec_state` mid-hold, the game's replies, and the recognition lines it logs)
  and stops at the first that produces `COMMAND: <callsign> …`. **Which variant
  commits is still to be confirmed in-game.** `CMD_RECOG_HELPER` still pushes
  the lexicon; the sender drains it.

### AIRPLANES `state` enum — DECODED (speed/alt calibration)
`states.py`: 1/2/6 = airborne (approach, high); 3/7 = short final / flare;
13 = rollout (fast on ground); 14 = pushback; 8/9/12/15/16 = ground stationary.
**`spd` is in KNOTS** (airborne 126–250) → `speed_to_mps = 0.514`. This fixed the
compression / on-final / RWSL timing (previously an un-calibrated guess).

### New message types this build adds (beyond the first decode)
`CMD_SET_CMD_TEXT` (command box / write path), `CMD_SOUND_STREAM` (audio, base64
PCM), `CMD_REQUEST_SCHEDULE`, `CMD_SELECT_AIRPLANE` (select + OK ack), and a
`CMD_RECOG_UPDATE` that now carries `{"btnRecognize":..,"airplanes":..}` state
rather than recognized text. UICFG can point at custom instrument packs
(`Airports/KBUR/instruments/ZAP FBI/...`).

## Safety

Loopback only. The core is a server accepting multiple clients, and connecting
an extra read-only client alongside the game's own is low-risk (the game
already runs 3+). Do **not** send writes until tested on a throwaway session —
`CMD_UPDATE_RUNWAY`/`CMD_SET_SEPARATION` change the running sim. Heed
TowerGlance's earlier note that live instrumentation once coincided with
crashes; keep a read-only client passive first.

## Provenance
`TS32.pcapng`: 114,479 packets, loopback, KBUR. Streams: data client
(14 MB core→client), TTS (10.8 MB), recog. Port 12020. Core version string
`v0.0.1.1`, TTS `v0.2025.349.1000`.
