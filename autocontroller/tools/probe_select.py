r"""Test the SELECT-then-inject hypothesis against the RUNNING game.

Every failed injection showed STATUS `selected_plane == 0`; the two that ever
executed had it non-zero. So the game commits an injected command only against
the SELECTED aircraft. This probe selects the target first (via
CMD_SELECT_AIRPLANE), confirms STATUS.selected_plane changed, then injects — and
reports, with hard evidence, whether selecting is the missing step.

It figures out the plane's id itself from CMD_REQUEST_AIRPLANES (name -> netidx),
and tries selecting by netidx and by callsign so we learn which the game wants.

Usage (game running, an aircraft with that callsign present):
    python tools\probe_select.py --log "<Player.log>" --cmd "n355fv runway 15 cleared to land"
    python tools\probe_select.py ... --port 12020 --hold 1.5
"""
from __future__ import annotations

import argparse
import json
import os
import select
import socket
import sys
import time

RECOG = {"greeting": {"name": "AIATC", "author": "self", "type": "RECOG",
                      "version": "v0.1", "description": "cmd", "security": "0"}}
DATA = {"greeting": {"name": "AIATCData", "author": "self", "type": "DATA",
                     "version": "v0.1", "description": "data", "security": "0"}}


class Conn:
    def __init__(self, host, port, greeting):
        self.sock = socket.create_connection((host, port), 5.0)
        self.sock.settimeout(5.0)
        self.buf = b""; self._id = 0
        self._raw(greeting)

    def _raw(self, obj):
        self.sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))

    def cmd(self, cmd, value="", **kw):
        self._id += 1
        m = {"cmd": cmd, "value": value, "id": self._id, "flags": 0, "func": None}
        m.update(kw); self._raw(m)

    def drain(self, wait=0.0):
        out = []; end = time.monotonic() + wait
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
                        pass
            if time.monotonic() >= end:
                break
        return out

    def reply(self, cmd, budget=3.0):
        self.cmd(cmd)
        end = time.monotonic() + budget
        while time.monotonic() < end:
            for m in self.drain(0.2):
                if m.get("cmd") == cmd and m.get("value"):
                    v = m["value"]
                    return json.loads(v) if isinstance(v, str) and v[:1] in "{[" else v
        return None


def selected(data):
    st = data.reply("CMD_REQUEST_STATUS") or {}
    return st.get("selected_plane")


def find_plane(data, callsign):
    planes = (data.reply("CMD_REQUEST_AIRPLANES") or {}).get("planes", [])
    up = callsign.upper()
    for p in planes:
        if str(p.get("name", "")).upper() == up:
            return p
    return None


def log_size(p):
    try:
        return os.path.getsize(p)
    except FileNotFoundError:
        return 0


def executed(log, start, callsign):
    try:
        with open(log, encoding="utf-8", errors="replace") as f:
            f.seek(start)
            body = f.read()
    except FileNotFoundError:
        return None, ""
    import re
    body = re.sub(r"</?color[^>]*>", "", body)
    hits = [l for l in body.splitlines()
            if l.startswith(("COMMAND:", "resp:", "recog_init", "recog_stop"))]
    ok = any(l.startswith("COMMAND: ") and callsign.upper() in l.upper() for l in body.splitlines())
    return ok, "\n".join("     " + h for h in hits[:12])


def try_select(cmdc, data, plane, callsign):
    """Ensure the target is selected; return (how, selected_value). Success is
    'the target IS selected' (selected_plane == its netidx), whether we changed
    it or it was already selected."""
    netidx = plane.get("netidx"); name = plane.get("name", callsign)
    cur = selected(data)
    if netidx is not None and cur == netidx:
        print(f"  target already selected (selected_plane={cur}); no select needed")
        return "already", cur
    attempts = []
    if netidx is not None:
        attempts += [("netidx-int", netidx), ("netidx-str", str(netidx))]
    attempts += [("callsign", name)]
    for how, val in attempts:
        cmdc.cmd("CMD_SELECT_AIRPLANE", value=val)
        time.sleep(0.4)
        cmdc.drain(0.3)
        after = selected(data)
        print(f"  select by {how:11} value={val!r:>10}: selected_plane -> {after} "
              f"(want {netidx})")
        if netidx is not None and after == netidx:
            return how, after
    return None, selected(data)


def inject(cmdc, text, hold, hz):
    period = 1.0 / hz
    end = time.monotonic() + hold
    n = 0
    while time.monotonic() < end:
        cmdc.cmd("CMD_SET_CMD_TEXT", value=text, flags=1)
        n += 1
        time.sleep(period)
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True)
    ap.add_argument("--cmd", required=True, help='e.g. "n355fv runway 15 cleared to land"')
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=12020)
    ap.add_argument("--hold", type=float, default=1.5)
    ap.add_argument("--hz", type=float, default=10.0)
    args = ap.parse_args()

    text = " ".join(args.cmd.split()).lower()
    callsign = text.split()[0]
    print(f"probe_select: port {args.port}  cmd={text!r}  target={callsign.upper()}")

    try:
        cmdc = Conn(args.host, args.port, RECOG)
        data = Conn(args.host, args.port, DATA)
    except OSError as e:
        print(f"cannot connect: {e}"); return 2
    cmdc.drain(1.0); data.drain(0.5)

    plane = find_plane(data, callsign)
    if not plane:
        print(f"  aircraft {callsign.upper()} not found in CMD_REQUEST_AIRPLANES — "
              f"is it present right now? (try a callsign currently on frequency)")
        return 1
    print(f"  found {plane.get('name')}: netidx={plane.get('netidx')} state={plane.get('state')} "
          f"own={plane.get('own')}")
    print(f"  selected_plane before anything: {selected(data)}")

    how, sel = try_select(cmdc, data, plane, callsign)
    if how is None:
        print("\n  RESULT: could NOT select the aircraft by any method. "
              "CMD_SELECT_AIRPLANE value format is different — paste this output.")
        return 1
    print(f"\n  SELECTED via {how} (selected_plane={sel}). Now injecting with the plane selected...")

    start = log_size(args.log)
    # keep it selected, open session (both), stream text, release
    if how != "already":
        cmdc.cmd("CMD_SELECT_AIRPLANE", value=(plane.get("netidx") if how.startswith("netidx") else plane.get("name")))
    cmdc.cmd("CMD_SET_PTT_STATE", value="true")
    cmdc.cmd("CMD_RECOG_UPDATE", value=json.dumps({"btnRecognize": True, "airplanes": ""}))
    time.sleep(0.3)
    n = inject(cmdc, text, args.hold, args.hz)
    time.sleep(0.4)
    cmdc.cmd("CMD_RECOG_UPDATE", value=json.dumps({"btnRecognize": False, "airplanes": ""}))
    cmdc.cmd("CMD_SET_PTT_STATE", value="false")
    print(f"  streamed {n} text msgs while selected; released.")
    time.sleep(2.5)
    ok, hits = executed(args.log, start, callsign)
    print("  Player.log:")
    print(hits or "     (no recognition lines)")
    print("\n" + "=" * 64)
    if ok:
        print(f" IT WORKED: selecting first, then injecting, executed the command.")
        print(f" -> the fix is CMD_SELECT_AIRPLANE (by {how}) before every command.")
    else:
        print(" Still EMPTY even though the aircraft was selected — so being selected\n"
              " is NOT sufficient. The missing piece is elsewhere. Paste this output.")
    print("=" * 64)
    cmdc.sock.close(); data.sock.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
