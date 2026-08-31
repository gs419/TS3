"""Command delivery back into the game.

DryRunSender is the default and always safe. KeyboardSender types into the
game's command box via synthetic keystrokes (Windows only; pip install
pyautogui pygetwindow). TcpProbeSender is an experimental stub for the
voice-pipeline / Communication Port routes documented in
docs/AI-CONTROLLER-FEASIBILITY.md.
"""
from __future__ import annotations

import time


class DryRunSender:
    def send(self, text: str) -> None:
        print(f"[DRY-RUN] would type: {text}")


class KeyboardSender:
    """Types `text` + Enter into the focused game window.

    Calibrate first (README): confirm the game accepts a full
    '<CALLSIGN> <COMMAND>' line in its text box, and whether a key must be
    pressed to focus the box. If so, set `focus_key`.
    """

    def __init__(self, window_title: str = "Tower! Simulator 3",
                 focus_key: str | None = None,
                 type_interval: float = 0.02):
        import pyautogui       # noqa: F401  (fail fast if missing)
        import pygetwindow
        self._pyautogui = __import__("pyautogui")
        self._gw = pygetwindow
        self.window_title = window_title
        self.focus_key = focus_key
        self.type_interval = type_interval
        self._pyautogui.FAILSAFE = True  # mouse to top-left corner aborts

    def send(self, text: str) -> None:
        wins = self._gw.getWindowsWithTitle(self.window_title)
        if not wins:
            print(f"[keyboard] window '{self.window_title}' not found; "
                  f"skipping: {text}")
            return
        win = wins[0]
        if not win.isActive:
            win.activate()
            time.sleep(0.15)
        if self.focus_key:
            self._pyautogui.press(self.focus_key)
            time.sleep(0.05)
        self._pyautogui.typewrite(text, interval=self.type_interval)
        self._pyautogui.press("enter")
        print(f"[keyboard] typed: {text}")


class PortCommandSender:
    """Injects commands over the Communication Port using CMD_SET_CMD_TEXT, the
    mechanism decoded from a live capture: the recognizer pushes the command
    text into the game's command box as
        {"cmd":"CMD_SET_CMD_TEXT","value":"<callsign> <command words>","flags":1}
    and the game parses/executes it. We mimic that.

    The command TEXT is the phraseology the game accepts (callsign + words), e.g.
    "ups87 pushback approved expect runway 15". Our policies already emit that
    shape; `format_command` normalizes it.

    IMPORTANT — commit trigger unconfirmed: the capture showed the text building
    up with flags:1 (interim recognition). Whether the game executes on a
    complete valid string, on a final flags:0 message, or on a separate submit is
    not yet certain. `commit_flags` and `send_commit` make this configurable;
    confirm on a throwaway session before trusting it. Loopback only.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 12020,
                 greet: bool = True, ptt_commit: bool = True,
                 settle_s: float = 0.05, lowercase: bool = True):
        self._json = __import__("json")
        self._socket = __import__("socket")
        self._time = __import__("time")
        self.host, self.port = host, port
        self.greet = greet
        self.ptt_commit = ptt_commit      # bracket the text with PTT true/false
        self.settle_s = settle_s
        self.lowercase = lowercase
        self.sock = None

    def connect(self):
        self.sock = self._socket.create_connection((self.host, self.port), 5.0)
        if self.greet:
            self._raw({"greeting": {"name": "AIATC", "author": "self",
                                    "type": "RECOG", "version": "v0.1",
                                    "description": "command injector",
                                    "security": "0"}})
        return self

    def _raw(self, obj):
        if self.sock is None:
            self.connect()
        self.sock.sendall((self._json.dumps(obj) + "\n").encode("utf-8"))

    @staticmethod
    def format_command(text: str, lowercase: bool = True) -> str:
        t = " ".join(text.split())          # collapse whitespace
        return t.lower() if lowercase else t

    def send(self, text: str) -> None:
        cmd = self.format_command(text, self.lowercase)
        # Mimic the recognizer: press PTT, set the command text, release PTT.
        # The game streams recognition into the command box (cmdtxt) and executes
        # it on PTT release (rec_state -> false) — CMD_SET_PTT_STATE is the
        # port-side control for that (seen in the first capture).
        if self.ptt_commit:
            self._raw({"cmd": "CMD_SET_PTT_STATE", "value": "true",
                       "flags": 0, "func": None})
            self._time.sleep(self.settle_s)
        self._raw({"cmd": "CMD_SET_CMD_TEXT", "value": cmd, "flags": 1,
                   "func": None})
        if self.ptt_commit:
            self._time.sleep(self.settle_s)
            self._raw({"cmd": "CMD_SET_PTT_STATE", "value": "false",
                       "flags": 0, "func": None})   # release = execute
        print(f"[port] issued: {cmd}")

    def close(self):
        if self.sock:
            self.sock.close()
