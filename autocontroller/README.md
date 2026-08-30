# TS3 Auto-Controller (prototype)

Tails Tower! Simulator 3's `Player.log`, tracks arrivals, and automatically
issues `<CALLSIGN> RUNWAY <XX> CLEARED TO LAND` when a plane reports on final
and the runway is free. Dry-run by default — it prints what it would do.

Background and evidence: see `../docs/AI-CONTROLLER-FEASIBILITY.md`.

## Calibration status: DONE for the current build

`gamestate.py` is calibrated to this install's real logs (v1.5.x / MeloTTS) and
validated end-to-end — see `../docs/PLAYER-LOG-FORMAT.md`. It parses
`COMMAND:`, `PILOT:` (spoken, resolved to ICAO via `callsign_resolver.py`),
`CREATE SERVER AIRPLANE:`, and `Add Scoring:` lines. A replay over the real
logs tracked 52 planes, resolved all 8 on-final calls, and issued 4
clear-to-land commands while correctly holding 2 for runway occupancy.

If a future game update changes the format, re-check with:
`python main.py --log <path> --replay` (parses the whole log, prints
reconstructed plane states), then adjust `PATTERNS` in `gamestate.py`.

## Run live (dry-run)

```
python main.py --log <path-to-Player.log>
```

Watch a session: every time an arrival calls on final you should see
`[DRY-RUN] would type: ...` at the right moment. Tune `runway_cooldown_s` in
`policy.py` for your airport.

## Run for real (keyboard injection)

```
pip install pyautogui pygetwindow
python main.py --log <path> --send keyboard
```

- Confirm in-game that typing `<CALLSIGN> RUNWAY 24 CLEARED TO LAND` into the
  command box works with the box focused; if a key is needed to focus it, pass
  `--focus-key <key>`.
- pyautogui's failsafe is on: slam the mouse into the top-left corner to abort.
- Start on an easy shift (KBDL) before letting it loose on KATL.

## Safety / design notes

- One outstanding landing clearance per runway + cooldown; go-around releases
  the runway; unacknowledged commands retried once, then left to the human.
- The bot only ever *adds* a clearance; it never cancels, deletes, or handles
  ground. You remain the controller of record.
- Next steps, in order of value: verify current-build log prefixes; add
  `CONTACT DEPARTURE` after touchdown/takeoff; runway-exit commands; then
  investigate the voice-pipeline TCP injection (senders.TcpProbeSender) to
  drop the keyboard-focus requirement.
