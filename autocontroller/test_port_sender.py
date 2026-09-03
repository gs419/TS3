"""Functional test of the port write path against a FAKE game core.

Stands up a tiny loopback TCP server that behaves like the Communication Port
(greets, answers CMD_REQUEST_STATUS, records every client message, and can push
unsolicited junk like the real core's lexicon re-pushes), then drives
PortCommandSender through it and asserts the exact message sequence the live
test showed is needed:

  session open -> text streamed repeatedly while held -> session close

Also covers: the four session modes, the socket drain (unsolicited pushes don't
stall anything), and recovery when the core drops the connection mid-session
(send() logs, closes, and the NEXT send reconnects instead of crashing).

Run: python test_port_sender.py
"""
from __future__ import annotations

import json
import socket
import threading
import time

from senders import PortCommandSender


class FakeCore:
    def __init__(self, push_junk: bool = False, drop_after: int = -1):
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        self.msgs: list = []            # (conn_index, dict)
        self.conns = 0
        self.push_junk = push_junk
        self.drop_after = drop_after    # close the conn after N client messages
        self._stop = False
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while not self._stop:
            try:
                self.srv.settimeout(0.2)
                c, _ = self.srv.accept()
            except socket.timeout:
                continue
            idx = self.conns; self.conns += 1
            threading.Thread(target=self._client, args=(c, idx), daemon=True).start()

    def _client(self, c, idx):
        buf = b""; n = 0
        c.sendall(b'{"welcome":{"security check":"fail/pass","core":"Fake"}}\r\n')
        if self.push_junk:
            c.sendall((json.dumps({"cmd": "CMD_RECOG_HELPER", "value": "x" * 200_000}) + "\r\n").encode())
        try:
            while True:
                chunk = c.recv(65536)
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    o = json.loads(line)
                    self.msgs.append((idx, o)); n += 1
                    if o.get("cmd") == "CMD_REQUEST_STATUS":
                        c.sendall((json.dumps({"cmd": "CMD_REQUEST_STATUS",
                                               "value": json.dumps({"cmdtxt": "", "rec_state": False})})
                                   + "\r\n").encode())
                    if self.drop_after >= 0 and n >= self.drop_after:
                        c.close(); return
        except OSError:
            return

    def cmds(self, idx=None):
        return [o for i, o in self.msgs if (idx is None or i == idx) and "cmd" in o]

    def stop(self):
        self._stop = True
        self.srv.close()


def _sender(core, **kw):
    s = PortCommandSender("127.0.0.1", core.port, settle_s=0.05, hold_s=0.4,
                          stream_hz=20.0, **kw)
    s.connect()
    return s


def test_ptt_mode_sequence():
    core = FakeCore()
    try:
        s = _sender(core, ptt_mode="ptt")
        s.send("SKW6353  RUNWAY 15   CLEARED TO LAND")
        time.sleep(0.2)
        seq = core.cmds()
        kinds = [(m["cmd"], m.get("value")) for m in seq]
        assert kinds[0] == ("CMD_SET_PTT_STATE", "true"), kinds[:3]
        assert kinds[-1] == ("CMD_SET_PTT_STATE", "false"), kinds[-3:]
        texts = [m for m in seq if m["cmd"] == "CMD_SET_CMD_TEXT"]
        assert len(texts) >= 5, f"text must be STREAMED while held, got {len(texts)}"
        assert all(m["value"] == "skw6353 runway 15 cleared to land" for m in texts)
        assert all(m["flags"] == 1 for m in texts)
        assert not any(m["cmd"] == "CMD_RECOG_UPDATE" for m in seq)
        # every text message sits strictly between press and release
        i_press = 0; i_rel = len(kinds) - 1
        assert all(i_press < i < i_rel for i, m in enumerate(seq) if m["cmd"] == "CMD_SET_CMD_TEXT")
        s.close()
    finally:
        core.stop()


def test_btn_both_none_modes():
    for mode, has_ptt, has_btn, has_flag0 in (("btn", False, True, False),
                                              ("both", True, True, False),
                                              ("none", False, False, True)):
        core = FakeCore()
        try:
            s = _sender(core, ptt_mode=mode)
            s.send("ups87 pushback approved expect runway 15")
            time.sleep(0.2)
            seq = core.cmds()
            assert any(m["cmd"] == "CMD_SET_PTT_STATE" for m in seq) == has_ptt, mode
            btn = [json.loads(m["value"]) for m in seq if m["cmd"] == "CMD_RECOG_UPDATE"]
            assert bool(btn) == has_btn, mode
            if has_btn:
                assert btn[0]["btnRecognize"] is True and btn[-1]["btnRecognize"] is False
            flag0 = [m for m in seq if m["cmd"] == "CMD_SET_CMD_TEXT" and m["flags"] == 0]
            assert bool(flag0) == has_flag0, mode
            s.close()
        finally:
            core.stop()


def test_drains_unsolicited_pushes():
    core = FakeCore(push_junk=True)
    try:
        s = _sender(core, ptt_mode="ptt")
        for _ in range(3):
            s.send("n355fv runway 15 cleared to land")
        assert s._drained > 100_000, "unsolicited pushes must be drained, not left in the window"
        s.close()
    finally:
        core.stop()


def test_recovers_when_core_drops_connection():
    core = FakeCore(drop_after=3)      # core closes after 3 messages (mid-stream)
    try:
        s = _sender(core, ptt_mode="ptt")
        s.send("skw6353 runway 15 cleared to land")   # must NOT raise
        # a later send reconnects (new connection index) and completes normally
        core.drop_after = -1
        s.send("jsx1877 runway 15 cleared to land")
        time.sleep(0.2)
        assert core.conns >= 2, "second send should have reconnected"
        last = core.cmds(core.conns - 1)
        assert last[0]["cmd"] == "CMD_SET_PTT_STATE" and last[-1]["value"] == "false"
        s.close()
    finally:
        core.stop()


def test_release_is_always_sent_on_close():
    core = FakeCore()
    try:
        s = _sender(core, ptt_mode="both")
        s.close()
        time.sleep(0.2)
        seq = core.cmds()
        assert any(m["cmd"] == "CMD_SET_PTT_STATE" and m["value"] == "false" for m in seq)
    finally:
        core.stop()


if __name__ == "__main__":
    test_ptt_mode_sequence();                print("  ok ptt mode: press -> streamed text -> release")
    test_btn_both_none_modes();              print("  ok btn / both / none modes")
    test_drains_unsolicited_pushes();        print("  ok drains unsolicited pushes")
    test_recovers_when_core_drops_connection(); print("  ok recovers when the core drops the connection")
    test_release_is_always_sent_on_close();  print("  ok release sent on close")
    print("all port-sender tests PASSED")
