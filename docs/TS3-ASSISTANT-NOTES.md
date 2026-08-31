# TS3 Assistant (CuratedPile) — observed capabilities & what it confirms

Notes from the in-app "About" pages of **TS3 Assistant — Automated Strip
Management** (v0.5.25138, updated May 18 2025; CuratedPile, FeelThere forum
"TS3 Assistant"). It's a mature strip-management / situational-awareness tool the
user runs. Several things it does confirm or sharpen our own findings.

## Confirms our decode
- **Live telemetry = the Communication Port.** A status light is **green when
  connected to the live session** (telemetry linked), orange when reading an
  offline log. That's the same port channel we decoded.
- **Player.log path confirmed:** `%userprofile%\AppData\LocalLow\FeelThere Inc_\
  Tower! Simulator 3\`. `Ctrl+L` loads a log offline; `Ctrl+R` relinks live.
- Reads the same signals we parse: outstanding (unspoken) radio calls with
  priority, per-plane telemetry (position, **altitude AGL**, **speed KTS**),
  weight class (`/H`, `/J` super), runway/taxiway state, gate, etc.

## The important one: command issue IS possible, and the text format
The About page's delete tip:
> "…you can issue these two commands to that plane (you won't get a reply)
> **`,callsign; CANCEL`** and then **`,callsign; CONTACT DEPARTURE`**. This will
> update the Arrivals/Departure board…"

So an external tool **can inject commands** into TS3, and the command text format
is **`,<CALLSIGN>; <COMMAND>`** — leading comma, callsign, semicolon, command
(matching the game's typed-command grammar `#airplane1; COMMAND; PARAMETERS`).
Some commands are silent ("won't get a reply"); normal ones get the usual
readback. **This is the string format our `Sender` should emit** once we confirm
the channel.

What it does NOT tell us: the **wire channel** — whether TS3 Assistant types
those into the game (keystrokes/window message) or sends them over the
Communication Port. Our write-path capture still resolves that. **New, easier
capture option:** run TS3 Assistant, trigger its delete tip (`,cs; CANCEL` /
`,cs; CONTACT DEPARTURE`) on a throwaway plane, and capture the loopback — that
reveals exactly how a known command is injected, without depending on voice
recognition. This may crack the write path faster than the voice route.

## Strip-state model (useful reference)
Its bays are a clean phase taxonomy we can mirror in our world model / display:
- Departures: **PL DEP** (planned) → **GND DEP** (taxiing) → **SEQ DEP**
  (sequenced) → **RWY** (shared) → **AB DEP** (airborne, awaiting handoff).
- Arrivals: **AB ARR** (approach→landing clearance) → **SEQ ARR** (cleared to
  land) → **RWY** → **GND ARR** (landed, taxiing).
- Plus FLT INFO. Color coding: green=ready, yellow=waiting-for-something,
  red=needs attention, magenta=lined up, orange=synced with in-game strip,
  blue=arrivals. Sequence numbers; "Departure Sequencing Mode" (Ctrl-Q) for
  manual ordering.

## Relationship to this project
Complementary, not the same:
- **TS3 Assistant** = human-in-the-loop strip management + awareness + manual
  departure sequencing; you keep TS3 focused and speak via PTT.
- **This project** = autonomous AI controllers (arrival/departure/ground/
  multi-position) that *decide and issue* commands.
Our engine could run alongside it, or its telemetry-link approach corroborates
ours. We don't copy it (closed-source); we note its observable behaviour.

## Live board (KBUR) — confirms our world-model data
Screens of the running tool show each strip carries exactly what we model, all
from telemetry (green link dot):
- callsign + registration (SKW1017 / N-number), type (CRJ7/B73W/E145),
  origin→dest (KBUR→KSFO), telephony (SKY WEST, SOUTHWEST, BIG STRIPE, EXECJET,
  AMERICAN, NOVEMBER), gate (G15 C1, A2 S1, A4 S1),
- assigned runway + taxi route as a compact code (`15 @A`, `S1 A 15`,
  `taxi 15`), status (`appr`, `LAND :03`, `TAXI :00`) with a countdown timer,
- a colored state dot (green ready / red needs-attention / magenta lined-up),
  AGL altitude (`+182`, `5,851'`), speed, and a priority color bar.
- **Gates panel:** a live per-terminal grid — Terminal A (A1–A9), B (B1–B5),
  C (C1–C4), D (D1–D5), G (G11–G16), M (M1–M7) — with **occupied (blue) vs open
  (yellow)** gates. That's live gate availability straight from telemetry, which
  is exactly the input `assignment.assign_gate` wants (occupied-gate set) — we
  can source it from the port/strips instead of guessing.

## Actionable takeaways for us
1. Our `Sender` should format commands as `,<CALLSIGN>; <COMMAND>` (confirm
   against the capture).
2. Best next capture: grab the loopback while TS3 Assistant issues a known
   command (its delete tip) — clean, user-triggered, reveals the write channel.
3. Mirror the bay/phase taxonomy and color semantics in our world model / the
   situational display feed.
4. Source **live gate occupancy** for `assignment.assign_gate` from the port
   strips (occupied vs open), rather than passing a guessed occupied set.
