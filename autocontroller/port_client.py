"""Read-only client for the TS3 Communication Port (decoded protocol).

Connects to the game core's loopback TCP server, performs the greeting/welcome
handshake as a data client, then polls live aircraft/status/strips. Prints a
compact radar view. READ-ONLY: it never sends control or recog writes.

Protocol reference: ../docs/PORT-PROTOCOL-DECODED.md

Usage (on the gaming PC, game running in a session):
    python port_client.py --port 12020        # port is settings-selectable
    python port_client.py --scan              # try common ports
"""
from __future__ import annotations

import argparse
import json
import math
import socket
import time

GREETING = {"greeting": {"name": "TowerGlanceRO", "author": "self",
                         "type": "DATA", "version": "v0.1", "description":
                         "read-only data client", "security": "0"}}


class PortClient:
    def __init__(self, host="127.0.0.1", port=12020, timeout=5.0):
        self.host, self.port, self.timeout = host, port, timeout
        self.sock = None
        self.buf = b""
        self._id = 0
        self.center = None  # (lat, lon) from CMD_REQUEST_AIRPORT

    # ---- connection ---------------------------------------------------
    def connect(self) -> dict:
        self.sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock.settimeout(self.timeout)
        self._send(GREETING)                       # greet
        # A welcome is expected but optional: if we don't get one quickly we
        # proceed anyway (the core also serves clients that skip the greeting).
        try:
            welcome = self._read_until(lambda m: "welcome" in m, budget=5)
            return welcome["welcome"]
        except (TimeoutError, ConnectionError):
            return {"core": "?", "version": "?", "security check": "unknown"}

    def close(self):
        if self.sock:
            self.sock.close()

    # ---- framing ------------------------------------------------------
    def _send(self, obj: dict):
        self.sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))

    def _request(self, cmd: str, value: str = ""):
        self._id += 1
        self._send({"cmd": cmd, "value": value, "id": self._id, "flags": 0, "func": ""})

    def _lines(self):
        """Yield decoded JSON objects as they arrive."""
        while True:
            while b"\n" in self.buf:
                line, self.buf = self.buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
            chunk = self.sock.recv(65536)
            if not chunk:
                return
            self.buf += chunk

    def _read_until(self, pred, budget=200):
        for msg in self._lines():
            if pred(msg):
                return msg
            budget -= 1
            if budget <= 0:
                raise TimeoutError("expected message not seen")
        raise ConnectionError("stream closed")

    def _reply(self, cmd: str):
        """Send a request and return the decoded inner value of its reply."""
        self._request(cmd)
        msg = self._read_until(lambda m: m.get("cmd") == cmd and m.get("value"))
        v = msg["value"]
        return json.loads(v) if isinstance(v, str) and v[:1] in "{[" else v

    # ---- high-level reads --------------------------------------------
    def airport(self):
        a = self._reply("CMD_REQUEST_AIRPORT")
        self.center = (a.get("_centerlat"), a.get("_centerlon"))
        return a

    def status(self):
        return self._reply("CMD_REQUEST_STATUS")

    def airplanes(self):
        return self._reply("CMD_REQUEST_AIRPLANES").get("planes", [])

    def strips(self):
        return self._reply("CMD_REQUEST_STRIPS").get("strips", [])

    # ---- helpers ------------------------------------------------------
    def local_to_latlon(self, pos):
        """Approx local ENU meters -> lat/lon using airport center."""
        if not self.center or self.center[0] is None:
            return None
        lat0, lon0 = self.center
        dlat = pos["z"] / 111_320.0
        dlon = pos["x"] / (111_320.0 * math.cos(math.radians(lat0)))
        return (lat0 + dlat, lon0 + dlon)


def render(pc: PortClient):
    ap = pc.airport()
    print(f"Airport: {ap.get('icao')} {ap.get('name')}  "
          f"wind {ap.get('_winddir')}@{ap.get('_windforce')}")
    while True:
        st = pc.status()
        planes = pc.airplanes()
        print(f"\n[{time.strftime('%H:%M:%S')}] state={st.get('game_state')} "
              f"speed={st.get('speed')} planes={len(planes)}")
        for p in planes:
            ll = pc.local_to_latlon(p.get("pos", {}))
            llstr = f"{ll[0]:.4f},{ll[1]:.4f}" if ll else "-"
            print(f"  {p['name']:8s} st={p.get('state'):>2} "
                  f"hdg={p.get('rot',{}).get('y',0):6.1f} spd={p.get('spd',0):6.1f} "
                  f"rwy={p.get('trgrw')} freq={p.get('own')} {llstr}")
        time.sleep(1.0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=12020)
    ap.add_argument("--scan", action="store_true",
                    help="probe common ports for the core listener")
    args = ap.parse_args()

    ports = [args.port] if not args.scan else [12020, 12030, 12010, 12040, 12000]
    for port in ports:
        pc = PortClient(args.host, port)
        try:
            w = pc.connect()
            print(f"Connected on {port}: core={w.get('core')} "
                  f"version={w.get('version')} security={w.get('security check')}")
            render(pc)
            return
        except (ConnectionRefusedError, OSError, TimeoutError) as e:
            print(f"port {port}: {e}")
        finally:
            pc.close()
    print("No core listener found. Is a session running? Check the "
          "Communication Port in game settings.")


if __name__ == "__main__":
    main()
