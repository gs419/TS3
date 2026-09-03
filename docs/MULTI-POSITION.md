# Multi-position AI ATC — split the airport among controllers

Divide an airport into controller positions (AI or human), each owning
areas/runways, and hand aircraft along a chain between them — including to and
from the human. Validated end-to-end on the "Cleveland" scenario.

## Why this fits the game natively

From the port's `CMD_REQUEST_FREQS`, the game already models position ownership:

| Frequency | Role | Owns areas |
| --- | --- | --- |
| 118.7 | TOWER | `8, 26, 15, 33` (the **runways**) |
| 123.9 | GROUND | `TerminalA…TerminalM` |
| 120.4 | DEPARTURE | `departure` |

- Every aircraft carries `own` = its controlling frequency.
- `CONTACT <freq>` hands an aircraft to another frequency; `own` updates.
- The airport ships the full taxiway graph: `roads[]` (95 taxiways with named
  node coordinates) + `holdpoints` — enough to define boundaries, crossing
  points, and hold-short handoff triggers.

So "positions own areas / runways on their own frequencies, and you hand off
between them" is the game's built-in model. Our layer just adds *more* positions
than the default two and drives the handoffs.

## The Cleveland scenario (validated)

Config in `positions.json` → `KCLE`:
- **Sally** (AI local, owns 24R) clears arrivals to land.
- **Bob** (AI ground, owns the area between 24R and 24L) routes the landed
  aircraft to a sensible crossing point.
- **You** (human local, own 24L) get the aircraft handed to you holding short
  of 24L; you clear it to cross.
- **RampAI** (AI ramp) takes it after the crossing and parks it.

Replay result:
```
initial:            DAL6221 -> Sally           (Sally clears to land 24R)
landed_on:24R       Sally -> Bob   CONTACT 121.9   (cross-frequency handoff)
holding_short:24L   Bob   -> Human (HUMAN alert)   (stand down, you take it)
crossed:24L         Human -> RampAI CONTACT 121.65
reached:ramp        RampAI -> (complete)
```

## How handoffs are chosen

`position_manager.PositionManager` transfers ownership on a matching handoff and
picks the mechanism automatically:
- **Cross-frequency** (Sally→Bob, Human→RampAI): issue `CONTACT <freq>` — the
  game moves the aircraft's `own` to the new controller.
- **Same-frequency** (e.g. splitting one tower freq between AI-24R and a human
  on 24L): a **virtual** transfer inside our layer — no game command, we just
  stop/start acting. Use this when the airport has one shared freq.
- **To the human**: stand down and alert; you control from there.

Ownership (`owner[callsign] -> position`) scopes every other policy: the
arrival/ground/ramp controller for a position only acts on aircraft it owns, so
Sally never touches Bob's traffic and neither touches yours.

## Designating who controls what

Everything is driven by `positions.json`, keyed per airport ICAO. Each
position:

| Field | Meaning |
| --- | --- |
| `name` | the controller's name ("Sally", "Bob", "Human") — shows in every log line |
| `role` | `local` \| `ground` \| `ramp` \| `departure` \| `clearance` |
| `kind` | **`ai`** or **`human`** — the switch that decides who works it |
| `frequency` | game frequency; decides CONTACT vs. virtual handoff |
| `owns_runways` | the runways this position clears (local/tower positions) |
| `owns_areas` | terminal groups / ground areas (ground/ramp positions) |

**Runway responsibility is enforced live.** `PositionMap.ai_owns_runway(rwy)`
is wired into the arrival and departure policies as an `owns_runway` gate: an
AI controller only acts on runways an **AI** position owns. A runway assigned to
a `human` position is left entirely alone (the log shows
`… — not my runway, leaving to its controller`), and arrivals on it are
assigned to the human position, so no AI handoff CONTACT is ever issued for
them. Validated on the real KBUR log in `test_multiposition.py`.

**Edit it with the GUI** — `python position_editor.py` serves a local page
(http://127.0.0.1:8765) where you pick the airport, set each position to an AI
name or *Human*, and pick the single owner of every runway from a matrix; Save
writes `positions.json` atomically. Or edit the JSON by hand.

Handoff `when` keys accept a trailing wildcard: `landed_on:*` matches a landing
on any runway, so one rule covers every runway a position owns.

## Semantic events that drive the chain

`landed_on:<rwy>`, `holding_short:<rwy>`, `crossed:<rwy>`, `reached:<area>`.
Where they come from (all from the game's own landing-state machine in
`Player.log`, see `PLAYER-LOG-FORMAT.md`):
- `landed_on` — emitted when an arrival goes `STATE_LAND →
  STATE_ESCAPE_RUNWAY` (rolled out and **vacated the runway**). That is the
  right tower→ground moment; a flyaway/go-around never emits it.
- `reached:ramp` — `… → STATE_TO_TERMINAL`. Completes the chain and releases
  ownership.
- `holding_short`, `crossed` — the plane's live position vs the airport
  `holdpoints`/`roads[]` geometry (world model + port feed). Need a small
  per-airport boundary definition; not yet emitted live.

## The live chain, as validated on the real KBUR log

```
SKW6353 on final 15         -> Local (ai local)           Local clears to land
STATE_LAND -> ESCAPE_RUNWAY -> Local -> Ground              "SKW6353 CONTACT GROUND"
(+2 s settle)                                             Ground: "SKW6353 TAXI TO RAMP"
STATE_TO_TERMINAL           -> Ground -> (complete)
```

The 2 s settle (`Orchestrator.handoff_settle_s`) keeps the CONTACT and the
ground controller's first call out of the same arbiter tick (the arbiter allows
one command per aircraft per tick) and reads naturally in-game.

CONTACT wording is role-based (`position_manager.contact_phrase`):
`CONTACT GROUND` / `CONTACT RAMP` / `CONTACT DEPARTURE` / `CONTACT TOWER` /
`CONTACT CLEARANCE`, falling back to `CONTACT <freq>`. `CONTACT DEPARTURE` is
confirmed in-game; if a build rejects one of the others, override the table
with `PositionManager.contact_phrases`.

## What's built vs. next

Built & validated (`positions.py`, `positions.json`, `position_manager.py`,
`orchestrator.py`, `live.py`):
- position map (areas/runways/freq/kind per position) + the GUI editor,
- ownership tracking, the full handoff state machine, CONTACT vs virtual vs
  human-alert selection, wildcard handoffs, the KCLE + KBUR maps,
- **per-position scoping** of the arrival/departure policies (`owns_runway`),
- the live tower→ground→ramp chain driven by the landing-state machine,
- the write path (`PortCommandSender`) behind the arbiter, run by `live.py`.

Next:
- **Routed ground taxi** in the live loop: the AI ground position currently
  issues the safe, known-good `TAXI TO RAMP`; swapping in `ground_controller`'s
  pathfinding (`TAXI VIA …` / `CROSS RUNWAY …`) needs the airport's taxi graph
  validated for the test airport.
- **Boundary geometry**: map `holdpoints`/areas to `holding_short`/`crossed`
  so the Cleveland-style human crossing handoff fires live.
- **Departure ownership**: departures are scoped by runway; assigning them to a
  ground position by terminal area (for the pushback→taxi handoff) is not
  wired yet.

## Naming your controllers

Positions carry a `name` ("Sally", "Bob"), so log/UI messages read naturally
("Sally clears DAL6221 to land 24R; handing to Bob"). With voices, each position
could even get a distinct TTS `voice_id` over the port's SAY channel.
