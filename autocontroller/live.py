"""Live runner: the assembled multi-position AI-ATC engine against the running
game. Tails Player.log for events, polls the Communication Port for live
geometry, and issues commands back through the port write path.

    python live.py --log "<path to Player.log>" --icao KBUR
    python live.py --log ... --icao KBUR --dry-run         # print only, send nothing
    python live.py --log ... --icao KBUR --runway 15       # default departure runway
    python live.py --log ... --icao KBUR --port 12020      # Communication Port (game settings)

Who controls what comes from positions.json (edit it, or use position_editor.py).
LIVE MODE SENDS REAL COMMANDS: the write path is CMD_SET_CMD_TEXT bracketed by
CMD_SET_PTT_STATE (decoded from captures; see docs/PORT-PROTOCOL-DECODED.md).
Try it on a throwaway session first.
"""
from __future__ import annotations

import argparse
import sys

from config import Config
from orchestrator import Orchestrator
from positions import PositionMap
from senders import DryRunSender, PortCommandSender
from port_client import PortClient

PRIME_PREFIXES = ("speech airplanes:", "CREATE SERVER AIRPLANE:")


def prime_from_existing_log(orch: Orchestrator, path: str) -> int:
    """The game prints its spoken-callsign dictionary and the roster early in
    a session; a live tail that starts mid-session would miss them. Feed just
    those lines (they never trigger clearances) so callsign resolution is
    exact from the first transmission."""
    n = 0
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith(PRIME_PREFIXES):
                    orch.feed_log(line); n += 1
    except FileNotFoundError:
        pass
    return n


def banner(pmap: PositionMap | None, icao: str, live: bool):
    print("=" * 64)
    print(f" AI-ATC live runner — {icao}   mode: {'LIVE (sending to game)' if live else 'DRY-RUN'}")
    print("=" * 64)
    if not pmap:
        print(f" no positions.json entry for {icao}: single AI controller owns all runways")
        return
    for p in pmap.positions.values():
        who = "HUMAN" if p.kind == "human" else "AI"
        owns = []
        if p.owns_runways: owns.append("rwy " + ", ".join(p.owns_runways))
        if p.owns_areas:   owns.append("areas " + ", ".join(p.owns_areas))
        print(f"  {p.name:10s} {who:5s} {p.role:10s} {p.frequency:7s} owns {'; '.join(owns) or '-'}")
    if pmap.handoffs:
        print("  handoffs: " + " | ".join(
            f"{h.when} {h.frm or '*'}->{h.to or '(done)'}" for h in pmap.handoffs))
    print("=" * 64)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True, help="path to Player.log")
    ap.add_argument("--icao", required=True, help="airport ICAO, e.g. KBUR")
    ap.add_argument("--port", type=int, default=12020, help="Communication Port")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--runway", default="", help="default departure runway")
    ap.add_argument("--dry-run", action="store_true", help="print commands, send nothing")
    ap.add_argument("--no-port-read", action="store_true",
                    help="don't poll the port for positions (log-only events)")
    ap.add_argument("--no-ptt", action="store_true",
                    help="send CMD_SET_CMD_TEXT without the PTT bracket")
    args = ap.parse_args()

    live = not args.dry_run
    cfg = Config(airport_icao=args.icao.upper(), default_runway=args.runway,
                 dry_run=not live)
    pmap = PositionMap.load(cfg.airport_icao)
    banner(pmap, cfg.airport_icao, live)

    # write path
    if live:
        sender = PortCommandSender(args.host, args.port, ptt_commit=not args.no_ptt)
        try:
            sender.connect()
            print(f"[live] command channel connected on {args.host}:{args.port}")
        except OSError as e:
            print(f"[live] cannot open command channel on port {args.port}: {e}\n"
                  f"       Is a session running? Check Settings > Communication Port. "
                  f"Falling back to DRY-RUN.")
            sender = DryRunSender(); live = False; cfg.dry_run = True
    else:
        sender = DryRunSender()

    # read path (live geometry); optional
    pc = None
    if not args.no_port_read:
        pc = PortClient(args.host, args.port)
        try:
            w = pc.connect()
            print(f"[live] data channel connected: core={w.get('core')} v{w.get('version')}")
        except OSError as e:
            print(f"[live] data channel unavailable ({e}); running on log events only")
            pc = None

    orch = Orchestrator(cfg, sender=sender, pmap=pmap)
    n = prime_from_existing_log(orch, args.log)
    print(f"[live] primed {n} roster/speech lines; "
          f"{len(orch.world.state.speech_map)} spoken callsigns known")
    try:
        orch.run(args.log, port_client=pc)
    except KeyboardInterrupt:
        print("\n[live] stopped")
    finally:
        if pc: pc.close()
        if hasattr(sender, "close"): sender.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
