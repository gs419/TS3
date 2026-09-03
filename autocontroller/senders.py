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
    """Types '<CALLSIGN> <COMMAND>' + Enter into the game's command text box.

    This bypasses the port recognizer entirely (which jams under sustained
    external sessions) — it drives the same typed command line a human uses.

    Calibrate once (see README):
      - window_title: the game window (substring match).
      - focus_key: a key that focuses/opens the command box, if the game needs
        one before typing (many builds: none — the box always takes keys; some:
        Enter to open). Leave None to type straight away.
      - clear_first: clear any leftover text before typing (Ctrl+A then Backspace)
        so a partial command never gets a new one appended to it.
      - The command is typed VERBATIM (upper-case, as the policies emit it) — the
        typed grammar matches the COMMAND: echoes; set lowercase=True if a build
        wants it lower.
    """

    def __init__(self, window_title: str = "Tower! Simulator 3",
                 focus_key: str | None = None,
                 type_interval: float = 0.02,
                 clear_first: bool = True,
                 lowercase: bool = False,
                 activate: bool = True,
                 focus_delay: float = 0.15,
                 click_xy: tuple | None = None):
        import pyautogui       # noqa: F401  (fail fast if missing)
        import pygetwindow
        self._pyautogui = __import__("pyautogui")
        self._gw = pygetwindow
        self.window_title = window_title
        self.focus_key = focus_key
        self.type_interval = type_interval
        self.clear_first = clear_first
        self.lowercase = lowercase
        self.activate = activate
        self.focus_delay = focus_delay
        self.click_xy = click_xy       # (x, y) of the command box, to click-focus it
        self._warned = False
        self._pyautogui.FAILSAFE = True  # mouse to top-left corner aborts

    def _focus_window(self) -> bool:
        if not self.activate:
            return True
        try:
            wins = self._gw.getWindowsWithTitle(self.window_title)
        except Exception:
            wins = []
        if not wins:
            if not self._warned:
                print(f"[keyboard] window '{self.window_title}' not found — "
                      f"typing into whatever is focused. Pass --window to fix.")
                self._warned = True
            return False
        win = wins[0]
        try:
            if not win.isActive:
                win.activate()
                time.sleep(0.15)
        except Exception:
            pass
        return True

    def send(self, text: str) -> None:
        cmd = " ".join(text.split())
        if self.lowercase:
            cmd = cmd.lower()
        self._focus_window()
        if self.click_xy:
            # click into the COMMAND window's "Enter command..." box to focus it
            self._pyautogui.click(self.click_xy[0], self.click_xy[1])
            time.sleep(self.focus_delay)
        if self.focus_key:
            self._pyautogui.press(self.focus_key)
            time.sleep(self.focus_delay)
        if self.clear_first:
            # select-all + delete, so a leftover partial command is replaced
            self._pyautogui.hotkey("ctrl", "a")
            self._pyautogui.press("backspace")
            time.sleep(0.02)
        self._pyautogui.typewrite(cmd, interval=self.type_interval)
        self._pyautogui.press("enter")
        print(f"[keyboard] typed: {cmd}")


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

    # How the recognition session is signalled around the text:
    #   "ptt"  CMD_SET_PTT_STATE true/false      (port PTT: confirmed to start/stop
    #                                            a session — recog_init/recog_stop)
    #   "btn"  CMD_RECOG_UPDATE {"btnRecognize"} (how FeelThere's recognizer module
    #                                            reports its own button)
    #   "both" both of the above
    #   "none" no session signalling; stream, then one flags:0 text
    MODES = ("ptt", "btn", "both", "none")

    def __init__(self, host: str = "127.0.0.1", port: int = 12020,
                 greet: bool = True, ptt_commit: bool = True,
                 settle_s: float = 0.5, lowercase: bool = True,
                 hold_s: float = 1.5, stream_hz: float = 10.0,
                 ptt_mode: str = "both", preseed_s: float = 0.4):
        self._json = __import__("json")
        self._socket = __import__("socket")
        self._select = __import__("select")
        self._time = __import__("time")
        self.host, self.port = host, port
        self.greet = greet
        self.ptt_mode = ptt_mode if ptt_commit else "none"
        if self.ptt_mode not in self.MODES:
            raise ValueError(f"ptt_mode must be one of {self.MODES}")
        self.settle_s = settle_s
        self.hold_s = hold_s
        self.stream_hz = stream_hz
        self.preseed_s = preseed_s   # populate the command box BEFORE PTT-down
        self.lowercase = lowercase
        self.sock = None
        self._drained = 0

    def connect(self):
        self.sock = self._socket.create_connection((self.host, self.port), 5.0)
        self.sock.settimeout(5.0)
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

    def _drain(self):
        """Discard whatever the game pushed to this client (welcome, lexicon
        re-pushes). Never block; without this a long session fills the receive
        window and the core's writes to us stall."""
        if self.sock is None:
            return
        try:
            while True:
                r, _, _ = self._select.select([self.sock], [], [], 0.0)
                if not r:
                    return
                chunk = self.sock.recv(1 << 16)
                if not chunk:
                    raise OSError("command channel closed by the game")
                self._drained += len(chunk)
        except (OSError, ValueError):
            raise

    def drain(self) -> None:
        """Idle drain for the tick loop: the core pushes STATUS snapshots to
        this client ~3/s even when we send nothing."""
        try:
            self._drain()
        except OSError as e:
            print(f"[port] command channel dropped while idle: {e} — will reconnect on the next command")
            try:
                if self.sock: self.sock.close()
            finally:
                self.sock = None

    def _session(self, down: bool):
        if self.ptt_mode in ("ptt", "both"):
            self._raw({"cmd": "CMD_SET_PTT_STATE", "value": "true" if down else "false",
                       "flags": 0, "func": None})
        if self.ptt_mode in ("btn", "both"):
            self._raw({"cmd": "CMD_RECOG_UPDATE",
                       "value": self._json.dumps({"btnRecognize": bool(down),
                                                  "airplanes": ""}),
                       "flags": 0, "func": None})

    @staticmethod
    def format_command(text: str, lowercase: bool = True) -> str:
        t = " ".join(text.split())          # collapse whitespace
        return t.lower() if lowercase else t

    def send(self, text: str) -> None:
        """Mimic FeelThere's recognizer module: open a recognition session, STREAM
        the command text repeatedly while it is held (the module re-sends the
        growing hypothesis ~10x/s for seconds; a single message sent right after
        the press executed as an empty command in a live test), then release.
        Any socket failure is logged and the channel reconnects on the next
        command instead of crashing the live loop."""
        cmd = self.format_command(text, self.lowercase)
        opened = False
        period = 1.0 / max(self.stream_hz, 0.5)

        def stream_until(deadline):
            k = 0
            while self._time.monotonic() < deadline:
                self._raw({"cmd": "CMD_SET_CMD_TEXT", "value": cmd, "flags": 1,
                           "func": None})
                k += 1
                self._time.sleep(period)
            return k

        try:
            self._drain()
            # The game samples the command box at/just after PTT-down (recog_init):
            # in a live capture an empty COMMAND was logged one line after
            # recog_init because the text hadn't been sent yet. So PRE-SEED the
            # box before opening the session, then keep streaming through the hold
            # so it is populated whenever the game reads it (init OR release).
            now = self._time.monotonic()
            n = stream_until(now + self.preseed_s)
            self._session(True); opened = True
            n += stream_until(self._time.monotonic() + self.hold_s)
            if self.ptt_mode == "none":
                self._raw({"cmd": "CMD_SET_CMD_TEXT", "value": cmd, "flags": 0,
                           "func": None})
            self._time.sleep(self.settle_s)
            self._session(False); opened = False     # release = execute
            print(f"[port] issued: {cmd}  (mode={self.ptt_mode}, {n} text msgs, "
                  f"preseed {self.preseed_s}s + hold {self.hold_s}s)")
        except OSError as e:
            print(f"[port] send FAILED for '{cmd}': {e} — will reconnect on the next command")
            if opened:
                try:
                    self._session(False)
                except OSError:
                    pass
            try:
                if self.sock:
                    self.sock.close()
            finally:
                self.sock = None

    def close(self):
        if self.sock:
            try:
                self._session(False)
            except OSError:
                pass
            self.sock.close()
            self.sock = None
