"""Probe the command write path against the RUNNING game, one variant at a
time, with hard evidence for each. Stops at the first variant that executes.

Background (docs/PORT-PROTOCOL-DECODED.md): a live test showed the port PTT
(CMD_SET_PTT_STATE) does start/stop a recognition session (recog_init /
recog_stop in Player.log), but a single CMD_SET_CMD_TEXT sent 50 ms after the
press executed as an EMPTY command. FeelThere's own recognizer module streams
the growing hypothesis ~80x over several seconds while the button is held and
signals its button with CMD_RECOG_UPDATE {"btnRecognize": true/false}. So the
candidates are about session signalling + holding + streaming:

  V1  PTT true            -> stream text ~1.2 s -> PTT false
  V2  btnRecognize true   -> stream text        -> btnRecognize false
  V3  PTT + btnRecognize  -> stream text        -> btnRecognize + PTT false
  V4  no session: stream text, then one flags:0 text

For each variant it prints: the game's STATUS cmdtxt / rec_state before, mid-
hold and after (did the text land in the box? was a session open?), anything
the game sent back on the command socket, and the recognition lines the game
wrote to Player.log (recog_init, ->:, FINAL, COMMAND:, resp:, recog_stop).

Usage (game running, session loaded; pick a REPEATABLE, harmless command for an
aircraft that exists right now, e.g. a landing clearance for the one on final):
    python tools\probe_write_path.py --log "<Player.log>" --cmd "skw6353 runway 15 cleared to land"
    python tools\probe_write_path.py ... --port 12020 --variants 1,2 --hold 2.0 --all
"""
from __future__ import annotations

import argparse
import json
import os
import select
import socket
import sys
import time

GREETING = {"greeting": {"name": "AIATC", "author": "self", "type": "RECOG",
                         "version": "v0.1", "description": "command injector",
                         "security": "0"}}
DATA_GREETING = {"greeting": {"name": "AIATCData", "author": "self", "type": "DATA",
                              "version": "v0.1", "description": "status poller",
                              "security": "0"}}
LOG_KEYS = ("recog_init", "recog_stop", "recog_cb", "->:", "FINAL:", "COMMAND:",
            "resp:", "Real commands", "unknown command", "requirement missing",
            "TOWER:", "REC:", "recv:")


class Conn:
    def __init__(self, host, port, greeting, name):
        self.name = name
        self.sock = socket.create_connection((host, port), 5.0)
        self.sock.settimeout(5.0)
        self.buf = b""
        self._id = 0
        self.send(greeting)

    def send(self, obj):
        self.sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))

    def req(self, cmd, value=""):
        self._id += 1
        self.send({"cmd": cmd, "value": value, "id": self._id, "flags": 0, "func": ""})

    def drain(self, wait=0.0):
        """Read whatever the game pushed; return decoded JSON lines."""
        out = []
        end = time.monotonic() + wait
        while True:
            r, _, _ = select.select([self.sock], [], [], max(0.0, end - time.monotonic()))
            if not r:
                break
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                break
            self.buf += chunk
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        out.append({"raw": line[:120].decode("utf-8", "replace")})
            if time.monotonic() >= end:
                break
        return out

    def reply(self, cmd, budget_s=3.0):
        self.req(cmd)
        end = time.monotonic() + budget_s
        while time.monotonic() < end:
            for m in self.drain(0.2):
                if m.get("cmd") == cmd and m.get("value"):
                    v = m["value"]
                    return json.loads(v) if isinstance(v, str) and v[:1] in "{[" else v
        return None


def status_line(data: Conn) -> str:
    st = data.reply("CMD_REQUEST_STATUS") or {}
    return (f"cmdtxt={st.get('cmdtxt')!r} rec_state={st.get('rec_state')} "
            f"rec_btn={st.get('rec_btn')} selected={st.get('selected_plane')!r}")


def press(cmdc: Conn, mode: str, down: bool):
    if mode in ("ptt", "both"):
        cmdc.send({"cmd": "CMD_SET_PTT_STATE", "value": "true" if down else "false",
                   "flags": 0, "func": None})
    if mode in ("btn", "both"):
        cmdc.send({"cmd": "CMD_RECOG_UPDATE",
                   "value": json.dumps({"btnRecognize": bool(down), "airplanes": ""}),
                   "flags": 0, "func": None})


def stream(cmdc: Conn, text: str, hold_s: float, hz: float, final_flag0: bool):
    period = 1.0 / hz
    end = time.monotonic() + hold_s
    n = 0
    while time.monotonic() < end:
        cmdc.send({"cmd": "CMD_SET_CMD_TEXT", "value": text, "flags": 1, "func": None})
        n += 1
        time.sleep(period)
    if final_flag0:
        cmdc.send({"cmd": "CMD_SET_CMD_TEXT", "value": text, "flags": 0, "func": None})
        n += 1
    return n


def tail_since(path: str, offset: int):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            lines = f.read().splitlines()
            return lines, f.tell()
    except FileNotFoundError:
        return [], offset


def log_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except FileNotFoundError:
        return 0


VARIANTS = {
    1: ("PTT true -> stream -> PTT false", "ptt", False),
    2: ("btnRecognize true -> stream -> btnRecognize false", "btn", False),
    3: ("PTT + btnRecognize -> stream -> release both", "both", False),
    4: ("no session: stream flags:1, then one flags:0", "none", True),
}


def run_variant(n, cmdc, data, args, callsign):
    title, mode, final0 = VARIANTS[n]
    print("\n" + "=" * 70)
    print(f" V{n}: {title}   (hold {args.hold}s @ {args.hz}/s, settle {args.settle}s)")
    print("=" * 70)
    start = log_size(args.log)
    print(f"  before : {status_line(data)}")
    junk = cmdc.drain(0.0)
    if junk:
        print(f"  (drained {len(junk)} pending message(s) from the game)")
    try:
        press(cmdc, mode, True)
        time.sleep(args.settle)
        # mid-hold status: is a session open, did the text land?
        t_mid = time.monotonic() + args.hold / 2
        sent = 0
        period = 1.0 / args.hz
        end = time.monotonic() + args.hold
        mid_done = False
        while time.monotonic() < end:
            cmdc.send({"cmd": "CMD_SET_CMD_TEXT", "value": args.cmd, "flags": 1, "func": None})
            sent += 1
            if not mid_done and time.monotonic() >= t_mid:
                print(f"  mid    : {status_line(data)}   (sent {sent} text msgs so far)")
                mid_done = True
            time.sleep(period)
        if final0:
            cmdc.send({"cmd": "CMD_SET_CMD_TEXT", "value": args.cmd, "flags": 0, "func": None})
            sent += 1
        time.sleep(args.settle)
    finally:
        press(cmdc, mode, False)
    print(f"  sent {sent} CMD_SET_CMD_TEXT message(s); released.")
    time.sleep(2.5)
    print(f"  after  : {status_line(data)}")
    replies = cmdc.drain(0.5)
    if replies:
        print(f"  game -> command socket ({len(replies)}):")
        for m in replies[:8]:
            s = json.dumps(m)
            print("     ", s[:160])
    lines, _ = tail_since(args.log, start)
    hits = [l for l in lines if any(k in l for k in LOG_KEYS)]
    print(f"  Player.log ({len(lines)} new lines, {len(hits)} recognition-related):")
    for l in hits[:40]:
        print("     ", l.replace("<color=#11CCCC>", "").replace("</color>", "")[:150])
    executed = any(l.startswith("COMMAND:") and callsign.upper() in l.upper() for l in lines)
    print(f"  RESULT : {'EXECUTED  <<<<<<<<<<  this is the write path' if executed else 'not executed'}")
    return executed


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True, help="path to Player.log")
    ap.add_argument("--cmd", required=True,
                    help='command text, e.g. "skw6353 runway 15 cleared to land"')
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=12020)
    ap.add_argument("--variants", default="1,2,3,4", help="which variants, in order")
    ap.add_argument("--hold", type=float, default=1.5, help="seconds to hold the session")
    ap.add_argument("--hz", type=float, default=10.0, help="text messages per second")
    ap.add_argument("--settle", type=float, default=0.3, help="gap after press / before release")
    ap.add_argument("--all", action="store_true", help="run every variant even after a success")
    ap.add_argument("--pause", type=float, default=4.0, help="seconds between variants")
    args = ap.parse_args()

    text = " ".join(args.cmd.split()).lower()
    args.cmd = text
    callsign = text.split()[0]
    order = [int(v) for v in args.variants.split(",") if v.strip()]

    print(f"probe: port {args.port}  cmd={text!r}  variants={order}")
    try:
        cmdc = Conn(args.host, args.port, GREETING, "cmd")
        data = Conn(args.host, args.port, DATA_GREETING, "data")
    except OSError as e:
        print(f"cannot connect to the game on {args.host}:{args.port}: {e}\n"
              f"Is a session running? Check Settings > Communication Port.")
        return 2
    w = cmdc.drain(1.0)
    print(f"command socket greeted; game replied with {len(w)} message(s): "
          + ", ".join(sorted({str(list(m)[0]) for m in w if m})) )
    print(f"status now: {status_line(data)}")

    winners = []
    try:
        for n in order:
            if n not in VARIANTS:
                print(f"unknown variant {n}"); continue
            if run_variant(n, cmdc, data, args, callsign):
                winners.append(n)
                if not args.all:
                    break
            time.sleep(args.pause)
    finally:
        # never leave a session open
        try:
            press(cmdc, "both", False)
        except OSError:
            pass
        cmdc.sock.close(); data.sock.close()

    print("\n" + "=" * 70)
    if winners:
        print(f" WRITE PATH CONFIRMED: variant(s) {winners} executed the command.")
        print(f" -> run live.py with: --ptt-mode {VARIANTS[winners[0]][1]} --hold {args.hold}")
    else:
        print(" No variant executed. Paste this whole output plus Player.log back.")
    print("=" * 70)
    return 0 if winners else 1


if __name__ == "__main__":
    sys.exit(main())
