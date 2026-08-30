# Port 12030 / the TS3 Communication Port — findings

Consolidated findings on Tower! Simulator 3's game-owned local TCP data channel
(the "Communication Port", observed on **12030**). This is the richest known
integration surface — richer than `Player.log` — but it is **undocumented and
not yet reverse-engineered by anyone publicly**.

## Prior art: has anyone decoded it?

**No.** A web and source survey (Aug 2026) found exactly one public reference to
this port anywhere: the research document in
[CrankyAnt/TowerGlance](https://github.com/CrankyAnt/TowerGlance), vendored in
this repo at
`community-sources/TowerGlance/docs/research/ts3-data-interface-inventory.md`.

- No published message schema, field list, client library, or protocol spec
  exists — for TS3 or the predecessor Tower!3D.
- Every *working* community tool deliberately avoids the port and reads
  `Player.log` instead (TS3CallsignHelper, TrafficVisualizer, the extensions
  repo). A grep of all vendored community sources finds the port referenced
  only in TowerGlance's markdown — no tool ships socket code against it.
- Tower!3D's only documented networking is its multiplayer netcode (community
  ports 21112 / 22222), which is unrelated peer-to-peer traffic and was never
  decoded for data extraction either.

So anyone decoding 12030 would be first — TowerGlance's analysis is the only
map, and it stops before the schema.

## What is established (from TowerGlance's capture)

Build observed: `v1.5.180.661s HDRP AI HOTFIX 2`, evidence dated 2026-08-02/03.

- **A game-owned loopback TCP listener** runs on the selected Communication
  Port (observed `12030`; the port is chosen from a fixed list in game
  settings). Loopback-only in the observations.
- **Lifecycle:** active in live single-player; absent in settings/menu; closed
  on the observed transition into multiplayer.
- **Consumers:** the main TS3 process plus the game-owned helpers `extwin`,
  `cpm`, `recog`, and `tts` all use connections associated with the listener.
  Two concurrent `extwin` instances connected simultaneously and visibly
  rendered live game panels — so full live panel state (ADIRS, strips) flows
  over this channel. FeelThere's own hotfix notes name "ADIRS on the external
  window", corroborating it.
- **The connection is bidirectional** (not a one-way feed).

### Format signature (aggregate only — no payload was retained)

From a bounded 5,000-frame external-window sample:

| Metric | Value |
| --- | --- |
| TCP payload frames | 5,000 |
| Total bytes | 3,129,262 |
| Printable ratio | 1.0 (all printable — no binary) |
| JSON-like frame starts | 3,331 |
| Newline-terminated frames | 3,331 |
| Null-byte ratio | 0 |
| TLS/compression magic bytes | 0 |
| Shannon entropy | 4.814 bits/byte |

**Interpretation:** the traffic is **plaintext, newline-delimited,
JSON-like framing** — human-readable and low-entropy, i.e. not encrypted or
compressed. TCP segmentation means record boundaries, request/response
pairing, message completeness, schema, and field meanings all remain
**unknown**. The signature supports only "printable JSON-ish lines", nothing
about content.

## What is NOT established

- No message schema, field names, or record structure — none was captured.
- No handshake, authorization, or client-semantics knowledge. Whether an
  arbitrary client may connect, and what a valid message looks like, is
  unknown.
- No safety profile for writing to the listener. It is bidirectional; a
  malformed write could disturb the running game.
- Whether the multiplayer-phase TCP `8080`/`8081` and changing UDP families
  are related (they appear to be separate multiplayer netcode, not this local
  channel).

## Safety caveat (from the source research)

TowerGlance's live probing hit **repeated game hangs/exits around their capture
tooling's shutdown** and they declared a "safety stop": no further live
instrumentation until a safe capture start/stop/cleanup method is validated.
Causality was never proven, but treat live capture as potentially destabilizing
— capture passively, keep game saves you don't care about, and never inject
into 12030 until the protocol is understood.

## Reverse-engineering path (open work)

Because the channel is plaintext JSON, decoding is very tractable — the barrier
is method safety, not obfuscation.

1. **Passive capture, read-only.** Sniff the `extwin`↔game loopback traffic
   while playing:
   - Wireshark on the loopback adapter (`\Device\NPF_Loopback` / npcap), filter
     `tcp.port == <configured port>`; or
   - a transparent localhost TCP proxy sitting between `extwin` and the game
     (point extwin at the proxy port, proxy forwards to the real port, log both
     directions).
2. **Correlate frames to on-screen state.** With plaintext JSON, read the
   frames directly and match fields to visible aircraft/strips/ADIRS values —
   fly one aircraft through a full arrival and watch which keys change.
3. **Document the schema incrementally** into this repo (a `port12030-schema/`
   folder): message types, the aircraft record shape, update cadence.
4. **Only then** consider a bounded, TowerGlance-owned read client, with
   explicit stop conditions, before ever attempting a write.

### Easier adjacent target: the recog→cpm path (port 9000)

The voice pipeline exposes a simpler seam. `recog.exe` serves recognized speech
on `127.0.0.1:9000` (see `RECOG/config/config.json`), and `cpm.exe`
fuzzy-matches that text against `Airports/commands.csv` before forwarding
structured commands to the game. Impersonating recog's transcript output to cpm
would let an external program **issue commands** without decoding the full
game-state protocol or touching the keyboard — you only mimic a short speech
string and let cpm do the translation. Same undocumented status, far smaller
message to reverse-engineer. This is the recommended first experiment for the
"act" side of an auto-controller (see `AI-CONTROLLER-FEASIBILITY.md`).

## Relationship to the auto-controller

- **Reading:** the auto-controller prototype (`../autocontroller/`) uses
  `Player.log` and needs nothing here. Port 12030 would only be needed for
  radar-grade data (positions, speeds, headings) that the log does not carry.
- **Writing:** port 9000 (recog→cpm) is the clean command-injection route;
  port 12030 is the last-resort, most-capable route and the only one that also
  removes the keyboard-focus requirement.

## Sources

- Vendored: `community-sources/TowerGlance/docs/research/ts3-data-interface-inventory.md`
  (primary evidence for everything above).
- [TowerGlance repository](https://github.com/CrankyAnt/TowerGlance) and its
  [issues](https://github.com/CrankyAnt/TowerGlance/issues) (no open decode of
  the port).
- Game files (OneDrive install): `RECOG/config/config.json` (recog `9000`, cpm
  fuzzy matching), `Airports/commands.csv` (command grammar).
- Web survey Aug 2026: no public reverse-engineering of the port found for TS3
  or Tower!3D; Tower!3D multiplayer ports (21112/22222) are unrelated netcode.
