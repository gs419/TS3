# Custom phraseology: "cleared direct X", "climb via SID"

Can we add commands like **"cleared direct LARKS"** or **"cleared for takeoff,
climb via the XYZ departure"**? Yes — as controller shorthand that we translate
into primitives the game executes. Not as new native game commands. Here's the
honest layering.

## Three layers, only two are ours to change

1. **Game parser (compiled, cannot change without a binary mod).** The core
   executes only the verbs in `commands.csv`: `FLY HEADING`, `TURN <dir>
   HEADING`, `TURN <dir> ON COURSE`, `CLIMB TO`, `ENTER FINAL RUNWAY`,
   `CHANGE TO RUNWAY`, `CLEARED FOR TAKEOFF`, `CONTACT DEPARTURE`, etc. There is
   **no** `DIRECT <fix>` and **no** `CLIMB VIA <SID>` verb, and no named-fix /
   waypoint navigation for airborne aircraft.
2. **Recognizer vocabulary (`commands.csv`, data — editable but limited).**
   This CSV feeds the speech recognizer (`cpm`). You can rephrase or alias
   existing verbs here, **but adding a row cannot create a new behavior** — the
   action for each command is hardcoded in `Assembly-CSharp.dll`/`FTL.dll`. A
   made-up `CLEARED DIRECT` row would be recognized as text and then do nothing.
3. **Our controller phraseology layer (`phraseology.py`, fully ours).** We
   accept the high-level shorthand and expand it into layer-1 primitives.

## What we synthesize (works, validated)

`phraseology.expand(intent, callsign, ctx)`:

| Shorthand | Expands to | Needs |
| --- | --- | --- |
| `direct <FIX>` | `FLY HEADING <bearing to fix>` (+`CLIMB TO`) | live plane pos (port) + fix lat/lon (nav data) + magvar |
| `climb via sid` | the SID's `CLIMB TO`/`FLY HEADING` legs, then `CONTACT DEPARTURE` | `sids.json` entry |
| `rejoin final <RWY>` | `ENTER FINAL RUNWAY <RWY>` | — |

The bearing math (`bearing_local`, `latlon_to_local`) is the inverse of the port
client's `local_to_latlon`, validated: a fix due north → heading 360, due east
→ 090. "Direct" = fly-the-heading-to-the-fix, re-issued as the aircraft drifts
(a vectored approximation of RNAV direct), not a true magenta-line LNAV.

Example (KBUR, magvar ~12°E):
```
direct LARKS   -> ['SWA1065 FLY HEADING 349', 'SWA1065 CLIMB TO 5000']
climb via sid  -> ['VXP165 FLY HEADING 175','VXP165 CLIMB TO 3000',
                   'VXP165 FLY HEADING 090','VXP165 CLIMB TO 5000',
                   'VXP165 CONTACT DEPARTURE']
```

## Takeoff clearance form

"Cleared for takeoff, climb via SID" becomes, using confirmed phrasing:
`RUNWAY <r> CLEARED FOR TAKEOFF AFTER DEPARTURE TURN <dir> ON COURSE ON
REACHING ALTITUDE <initial> CONTACT DEPARTURE` (from `departures.py`), and — if
you want the aircraft to actually fly the SID legs before handoff rather than be
handed off — follow it with the `climb via sid` leg commands while holding it on
tower frequency.

## Requirements & honest limits

- **Live position feed (port):** every geometric expansion (`direct`, closed-loop
  SID legs) needs the plane's `pos`/heading from `CMD_REQUEST_AIRPLANES`. Wire
  `port_client.py` into the world model first.
- **Nav data:** fix coordinates for `direct <FIX>` come from a fix database
  (FAA CIFP / OpenNav). `phraseology.expand` takes a `fixes` map; populate it.
- **Write path:** issuing the expanded commands needs the confirmed command-
  injection route (one voice-command capture).
- **It's vectoring, not LNAV.** The plane flies headings we compute; it won't
  self-navigate a fix or auto-correct for wind unless we close the loop
  (re-issue headings each tick from fresh positions). Good enough to "send it
  toward X"; not a true FMS direct.
- **True native direct-to** (a real waypoint-nav command, magenta line, wind
  correction) would need a **binary mod** (BepInEx + Harmony patch adding a
  command that drives the flight model to a fix) — a much larger, separate
  effort than this external layer.

## Files
- `autocontroller/phraseology.py` — the expander + geometry (validated).
- Uses `departures.py` (SID legs) and, at runtime, `port_client.py` (positions).
