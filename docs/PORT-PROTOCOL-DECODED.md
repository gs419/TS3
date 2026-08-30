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
- **Write / command injection (path identified, not yet confirmed):** the recog
  channel is the input. A client that greets as `recog`, accepts the lexicon,
  and emits `CMD_RECOG_UPDATE` with recognized command text should have the core
  parse it as if spoken. The exact "final/committed" form wasn't captured
  (values were empty — commands during capture were likely typed), so **one
  confirming capture is needed**: press PTT, speak one command, and grab the
  non-empty `CMD_RECOG_UPDATE`. Control writes (`CMD_UPDATE_RUNWAY`,
  `CMD_SET_SEPARATION`, `CMD_SET_PTT_STATE`) are already confirmed shapes.

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
