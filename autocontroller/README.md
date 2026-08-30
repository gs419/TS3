# TS3 Auto-Controller (prototype)

Tails Tower! Simulator 3's `Player.log`, tracks arrivals, and automatically
issues `<CALLSIGN> RUNWAY <XX> CLEARED TO LAND` when a plane reports on final
and the runway is free. Dry-run by default — it prints what it would do.

Background and evidence: see `../docs/AI-CONTROLLER-FEASIBILITY.md`.

## Calibrate first (once, on the gaming PC)

The log line formats are undocumented and build-dependent. Before trusting the
bot:

1. Play a short session (a couple of arrivals, issue clearances by hand), quit.
2. Find the log: `Win+R` → `%AppData%\..\LocalLow` → `FeelThere_*\Tower! Simulator 3\Player.log`.
3. Run `python main.py --log <path> --replay` — it parses the whole log and
   prints the plane states it reconstructed.
4. If nothing was detected, open Player.log and search for the command you
   typed and the pilot's "on final" call. Adjust the prefixes in
   `gamestate.py` `PATTERNS` to match your build (current builds may not use
   the `ADD TTS to Acapela:` prefix — look for whatever line carries pilot
   speech text).

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
