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

## Semantic events that drive the chain

`landed_on:<rwy>`, `holding_short:<rwy>`, `crossed:<rwy>`, `reached:<area>`.
Where they come from:
- `landed_on` — `Add Scoring: MSG_LANDING_SUCCESSFUL` + the plane's runway (log,
  have it now).
- `holding_short`, `crossed`, `reached:ramp` — the plane's live position vs the
  airport `holdpoints`/`roads[]` geometry (world model + port feed). These need
  the position feed wired (done) plus a small per-airport boundary definition.

## What's built vs. next

Built & validated (`positions.py`, `positions.json`, `position_manager.py`):
- position map (areas/runways/freq/kind per position),
- ownership tracking, the full handoff state machine, CONTACT vs virtual vs
  human-alert selection, and the KCLE + KBUR example maps.

Next to make it fully live:
- **Ground routing** (Bob's "route to a sensible crossing point"): pathfind on
  the `roads[]` graph to a crossing hold-short, emitting `TAXI VIA …` / `CROSS
  RUNWAY …`. The graph is in hand; the router is the work.
- **Boundary geometry**: map `holdpoints`/areas to the `holding_short`/`reached`
  events per airport.
- **Per-position controllers**: scope the existing arrival/ground policies to a
  position's owned aircraft (one line: filter by `mgr.current(cs)`).
- **Write path** (as always) to actually issue the CONTACT/taxi commands.

## Naming your controllers

Positions carry a `name` ("Sally", "Bob"), so log/UI messages read naturally
("Sally clears DAL6221 to land 24R; handing to Bob"). With voices, each position
could even get a distinct TTS `voice_id` over the port's SAY channel.
