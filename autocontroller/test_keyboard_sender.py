"""Test KeyboardSender's typing logic with fake pyautogui / pygetwindow.

Verifies it clears the box, types the command verbatim (upper-case), presses
Enter, focuses the window, and collapses whitespace — without needing the real
GUI libraries or a display.

Run: python test_keyboard_sender.py
"""
from __future__ import annotations

import sys
import types


class FakeAuto:
    FAILSAFE = True
    def __init__(self): self.calls = []
    def hotkey(self, *keys): self.calls.append(("hotkey",) + keys)
    def press(self, k): self.calls.append(("press", k))
    def typewrite(self, text, interval=0.0): self.calls.append(("type", text))
    def click(self, x, y): self.calls.append(("click", x, y))


class FakeWin:
    def __init__(self): self.isActive = False; self.activated = 0
    def activate(self): self.activated += 1; self.isActive = True


class FakeGW:
    def __init__(self, win): self._win = win
    def getWindowsWithTitle(self, title): return [self._win] if self._win else []


def _make(**kw):
    auto = FakeAuto(); win = FakeWin()
    sys.modules["pyautogui"] = types.SimpleNamespace(
        FAILSAFE=True, hotkey=auto.hotkey, press=auto.press, typewrite=auto.typewrite, click=auto.click)
    sys.modules["pygetwindow"] = FakeGW(win)
    import importlib, senders
    importlib.reload(senders)
    s = senders.KeyboardSender(**kw)
    # rebind to our recording fake (reload made a fresh __import__ target)
    s._pyautogui = types.SimpleNamespace(
        FAILSAFE=True, hotkey=auto.hotkey, press=auto.press, typewrite=auto.typewrite, click=auto.click)
    s._gw = FakeGW(win)
    return s, auto, win


def test_clears_types_and_enters():
    s, auto, win = _make()
    s.send("N355FV   RUNWAY 15   CLEARED TO LAND")
    seq = auto.calls
    assert ("hotkey", "ctrl", "a") in seq, seq
    assert ("press", "backspace") in seq, seq
    assert ("type", "N355FV RUNWAY 15 CLEARED TO LAND") in seq, seq   # whitespace collapsed, case kept
    assert seq[-1] == ("press", "enter"), seq
    # clear happens before typing
    assert seq.index(("hotkey", "ctrl", "a")) < seq.index(("type", "N355FV RUNWAY 15 CLEARED TO LAND"))
    assert win.activated == 1


def test_focus_key_and_no_clear_and_lowercase():
    s, auto, win = _make(focus_key="enter", clear_first=False, lowercase=True)
    s.send("UPS87 PUSHBACK APPROVED EXPECT RUNWAY 15")
    seq = auto.calls
    assert ("press", "enter") == seq[0], "focus_key pressed first"
    assert not any(c[0] == "hotkey" for c in seq), "clear disabled"
    assert ("type", "ups87 pushback approved expect runway 15") in seq, seq


def test_missing_window_still_types():
    s, auto, _ = _make()
    s._gw = FakeGW(None)          # no window found
    s.send("SWA606 RUNWAY 15 CLEARED FOR TAKEOFF")
    assert ("type", "SWA606 RUNWAY 15 CLEARED FOR TAKEOFF") in auto.calls, "should still type"


def test_click_to_focus_and_no_activate():
    s, auto, win = _make(click_xy=(500, 380), activate=False, clear_first=False)
    s.send("N355FV RUNWAY 15 CLEARED TO LAND")
    seq = auto.calls
    assert ("click", 500, 380) in seq, seq
    assert seq.index(("click", 500, 380)) < seq.index(("type", "N355FV RUNWAY 15 CLEARED TO LAND"))
    assert seq[-1] == ("press", "enter")
    assert win.activated == 0, "no-activate must not steal window focus"


if __name__ == "__main__":
    test_clears_types_and_enters();            print("  ok clears, types verbatim, enters, focuses")
    test_focus_key_and_no_clear_and_lowercase(); print("  ok focus_key / no-clear / lowercase options")
    test_missing_window_still_types();         print("  ok types even if window not found")
    test_click_to_focus_and_no_activate();     print("  ok click-to-focus + no-activate")
    print("all keyboard-sender tests PASSED")
