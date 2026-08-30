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


class TcpProbeSender:
    """EXPERIMENTAL. Placeholder for injecting text into the voice pipeline
    (recog serves on 127.0.0.1:9000; cpm matches text against commands.csv)
    or, later, JSON frames to the game's Communication Port (observed 12030).

    The wire formats are unverified — capture them first (e.g. run the game,
    use a localhost sniffer while speaking one command) before enabling this.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 9000):
        self.host, self.port = host, port

    def send(self, text: str) -> None:
        raise NotImplementedError(
            "Capture the recog/cpm wire format before enabling TCP injection "
            "— see docs/AI-CONTROLLER-FEASIBILITY.md")
