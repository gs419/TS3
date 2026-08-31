# AI controller roadmap — beyond clear-to-land

The right frame: one **shared world model** (built from the Communication Port
+ Player.log) feeding several independent **controller policies** (arrival,
departure, sequencing/safety). Each policy is small and rule-based to start;
any can later be swapped for an LLM policy. This doc grounds each requested
feature in the **actual command grammar** (`Airports/commands.csv`) and the data
we've decoded, and says honestly what each needs.

## What each data channel gives a policy

| Need | Source | Status |
| --- | --- | --- |
| Who exists, callsigns, spawns | log (`CREATE SERVER AIRPLANE`) + port (`AIRPLANES`) | ✅ have |
| Events: requests, on-final, takeoffs, outcomes | log (`PILOT`, `COMMAND`, `Add Scoring`) | ✅ calibrated |
| Geometry: position, heading, speed, spacing | port `CMD_REQUEST_AIRPLANES` (`pos`, `rot.y`, `spd`) | ✅ decoded, ⏳ needs live test |
| Issuing commands | recog channel (port) or typed keystrokes | ⏳ write path needs 1 confirming capture |

**Rule of thumb:** anything driven by *events* (departure flow, go-around
detection, forgot-departure nagging) works from the **log alone**. Anything
*geometric* (revectoring a go-around onto final, detecting compression) needs
the **port position feed**. Both need the **write path** confirmed to actually
act — until then every policy runs in dry-run/copilot mode (prints/《suggests》).

## 1. AI departure controller — HIGH feasibility, log-only

The whole flow is visible in the logs and every step is a `commands.csv` verb:

```
PILOT "requesting push and start"  -> PUSHBACK APPROVED EXPECT RUNWAY <r>
PILOT "ready to taxi"              -> RUNWAY <r> VIA <taxiways>   (+ CROSS RUNWAY <x> as needed)
at hold short                      -> RUNWAY <r> LINE UP AND WAIT
runway clear + spacing ok          -> RUNWAY <r> CLEARED FOR TAKEOFF
                                      [AFTER DEPARTURE TURN <L/R> ON COURSE] [ON REACHING ALT <a> CONTACT DEPARTURE]
airborne                           -> CONTACT DEPARTURE
```
Triggers come from `PILOT:` requests and `strips` (`dep:true`). Taxi routing
can start trivial (game accepts `RUNWAY <r> VIA <one taxiway>`) and later use
the airport `roads[]` graph from `CMD_REQUEST_AIRPORT` for real pathfinding.
Departure sequencing (who lines up next) is the interesting logic: one runway
occupant at a time, wake-turbulence spacing by `wc`/weight class, alternate
departures/arrivals on a shared runway. **This is the best next build** — it
parallels the arrival policy and is fully validatable on the captured logs.

## 2. Go-around revectoring — MEDIUM, needs position feed + write path

When a go-around happens (we issue it, or `PILOT`/`COMMAND` shows `GO AROUND`),
fly the aircraft a pattern back to final using the AIR/ARRIVAL verbs:
```
GO AROUND
FLY HEADING <upwind/crosswind>          (FLY_HEADING)
TURN <L/R> HEADING <downwind>           (TURN_HEADING)
CLIMB TO <alt>                          (CLIMB_TO)
... abeam the numbers + gap ...
TURN <L/R> HEADING <base> then <final>
ENTER FINAL RUNWAY <r>                   (ENTER_FINAL)   or CHANGE TO RUNWAY <r>
```
This is a geometric state machine: it needs each turn timed off the plane's
`pos`/`rot.y` relative to the runway threshold (from the port), so it can't run
on the log alone. Note the game's **AI TRACON already re-sequences arrivals to
final** — so first check whether a go-around is auto-rehandled; the custom
revector is most valuable when you want tighter/again-around control than the
built-in TRACON gives. Simplest robust version: `FLY HEADING` outbound, wait a
fixed distance, `TURN` back, `ENTER FINAL RUNWAY` — a teardrop, not a full
pattern.

## 3. Compression / spacing management — MEDIUM, needs position feed

Detect a trailing arrival closing on the leader on the same final: from the
port, project both onto the runway centerline and watch the in-trail gap
(distance / closure rate from `pos` + `spd`). When it drops below a threshold,
act.

**Honest limitation:** this sim's tower has **no speed-assignment command** —
there is no "reduce speed to 170 knots" in `commands.csv` (that's TRACON's job,
handled by the game AI). The spacing levers the tower *does* have:
- `MAKE SHORT APPROACH` — speed the **leader** up / tighten its path.
- `GO AROUND` — send the trailing one around (last resort, and the one thing
  that always works IFR).
- `MAKE <L/R> 360 FOR SPACING` and `EXTEND <downwind>` — real spacing tools but
  **VFR/pattern only**, so they apply to local/VFR traffic, not IFR finals.
- S-turns via `FLY HEADING` / `TURN` to stretch the trailing aircraft's path.
So a truthful "compression manager" is: **warn** on shrinking spacing always
(copilot value), and for VFR traffic use 360/extend; for IFR finals the only
tower action is short-approach-the-leader or go-around-the-trailer. Good to
build as a **safety-net/advisor** first — it prevents the `MSG_RUNWAY_SEPARATION`
scoring hits we can already see in the log.

## 4. Other high-value, low-effort additions

- **Forgot-departure nag / auto-handoff:** the log shows `MSG_FORGOT_DEPARTURE`
  penalties; watch for airborne departures still on tower and auto-issue
  `CONTACT DEPARTURE`. Log-only, trivial, immediately useful.
- **Runway-incursion & separation guardian:** watch `Add Scoring:
  MSG_RUNWAY_SEPARATION / MSG_GROUND_CLOSE / MSG_CRASH` and the port geometry;
  alert or auto-issue the save (`GO AROUND`, `CANCEL TAKEOFF`, `HOLD POSITION`).
- **Crossing-runway coordinator:** KBUR/KATL have intersecting runways
  (`RUNWAY CROSS ERROR: 8 x 26` appears in the log). A policy that tracks which
  runway is "hot" and issues/holds `CROSS RUNWAY` is high value at these fields.
- **LLM policy layer:** replace any rule engine with a Claude call that gets the
  world-model snapshot and returns a command validated against `commands.csv`
  before it's sent. The grammar makes output-validation trivial.
- **Trainer/debrief & live dashboard:** the world model + `Add Scoring` events
  are everything needed for a post-session grade or a real-time strip/radar web
  view (the TowerGlance idea, now buildable since the port is decoded).

## Suggested build order

1. **Departure controller** (log-only, validatable now) — biggest capability
   jump, parallels the arrival policy.
2. **Forgot-departure auto-handoff + separation guardian** (log-only, tiny) —
   quick wins that also protect score.
3. Confirm the **write path** (one voice-command capture) so 1–2 can actually
   act, not just dry-run.
4. **Live port client into the world model** (positions) — unlocks the geometric
   features.
5. **Go-around revector** and **compression advisor** (need positions).
6. **LLM policy** swap-in once the rule versions are trustworthy.

## Architecture note

Refactor toward: `WorldModel` (fed by `LogInterpreter` + `PortClient`) → a list
of `Policy` objects (`ArrivalPolicy`, `DeparturePolicy`, `SafetyPolicy`) each
emitting proposed commands → one `CommandArbiter` that de-conflicts (never two
clearances on one runway in the same tick), applies cooldowns, and hands the
final command to the `Sender`. This keeps each controller brain small and makes
adding the next one a new `Policy`, not a rewrite.
