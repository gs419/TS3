"""TS3 auto-controller prototype: tails Player.log, auto-clears arrivals to land.

Usage (on the gaming PC):
    python main.py --log "%AppData%\\..\\LocalLow\\FeelThere_...\\Tower! Simulator 3\\Player.log"
    python main.py --log <path> --replay        # parse whole log once, dry-run, exit
    python main.py --log <path> --send keyboard # actually type into the game

Default sender is dry-run: it only prints the commands it would issue.
"""
from __future__ import annotations

import argparse
import os
import time

from gamestate import GameState, LogInterpreter
from policy import AutoTowerPolicy
from senders import DryRunSender, KeyboardSender


def tail(path: str, replay: bool):
    """Yield log lines; follow the file, surviving truncation/rotation."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        if replay:
            yield from f
            return
        f.seek(0, os.SEEK_END)  # live mode: only new lines
        while True:
            line = f.readline()
            if line:
                yield line
            else:
                try:  # detect rotation/truncation
                    if os.stat(path).st_size < f.tell():
                        f.seek(0)
                except FileNotFoundError:
                    pass
                yield None  # idle tick


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--log", required=True, help="path to Player.log")
    ap.add_argument("--replay", action="store_true",
                    help="parse the existing log once (dry-run) and exit")
    ap.add_argument("--send", choices=["dry", "keyboard"], default="dry")
    ap.add_argument("--window", default="Tower! Simulator 3",
                    help="game window title for the keyboard sender")
    ap.add_argument("--focus-key", default=None,
                    help="key that focuses the game's command box, if any")
    args = ap.parse_args()

    sender = (KeyboardSender(args.window, args.focus_key)
              if args.send == "keyboard" and not args.replay else DryRunSender())

    state = GameState()
    policy = AutoTowerPolicy(state=state, sender=sender)
    interp = LogInterpreter(state, policy.on_event)

    print(f"[main] sender={type(sender).__name__} replay={args.replay}")
    last_tick = time.monotonic()
    for line in tail(args.log, args.replay):
        if line is not None:
            interp.feed(line)
        now = time.monotonic()
        if now - last_tick >= 1.0:
            policy.tick()
            last_tick = now
        if line is None:
            time.sleep(0.25)

    if args.replay:
        print("\n[main] replay complete. Final plane states:")
        for cs, p in sorted(state.planes.items()):
            print(f"  {cs:10s} {p.phase.name:16s} rwy={p.runway or '-'}")


if __name__ == "__main__":
    main()
