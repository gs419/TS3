"""Decision rules: the 'AI controller'. Basic version: clear arrivals to land.

Deliberately conservative — one outstanding landing clearance per runway,
cooldown between clearances, retry once if the game never echoes our command.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from gamestate import GameState, Phase, Plane


@dataclass
class PendingCommand:
    callsign: str
    text: str
    issued_at: float
    retries: int = 0


@dataclass
class AutoTowerPolicy:
    state: GameState
    sender: "object"          # any object with .send(text)
    runway_cooldown_s: float = 25.0
    echo_timeout_s: float = 6.0
    max_retries: int = 1
    enabled: bool = True

    _last_clearance_at: dict[str, float] = field(default_factory=dict)
    _pending: dict[str, PendingCommand] = field(default_factory=dict)

    # ---- event hooks from LogInterpreter ------------------------------
    def on_event(self, kind: str, plane: Plane) -> None:
        if kind == "on_final":
            self._maybe_clear_to_land(plane)
        elif kind in ("cleared_to_land", "readback_land"):
            # our command was echoed / read back: done
            self._pending.pop(plane.callsign, None)
        elif kind == "go_around":
            # runway freed; a queued arrival may now be clearable
            self._recheck_finals()

    # ---- periodic tick (call ~1/s) ------------------------------------
    def tick(self) -> None:
        now = time.monotonic()
        for cs, cmd in list(self._pending.items()):
            if now - cmd.issued_at > self.echo_timeout_s:
                if cmd.retries < self.max_retries:
                    cmd.retries += 1
                    cmd.issued_at = now
                    self.sender.send(cmd.text)
                else:
                    print(f"[policy] no echo for '{cmd.text}' after retries; "
                          f"leaving {cs} to the human")
                    self._pending.pop(cs, None)

    # ---- rules --------------------------------------------------------
    def _maybe_clear_to_land(self, plane: Plane) -> None:
        if not self.enabled or not plane.runway:
            return
        rwy = plane.runway
        holder = self.state.runway_reserved_by.get(rwy)
        if holder and holder != plane.callsign:
            print(f"[policy] {plane.callsign} on final {rwy}, but {holder} "
                  f"holds the runway — waiting")
            return
        last = self._last_clearance_at.get(rwy, 0.0)
        if time.monotonic() - last < self.runway_cooldown_s:
            print(f"[policy] {plane.callsign} on final {rwy} — cooldown, waiting")
            return
        if plane.callsign in self._pending or plane.phase == Phase.CLEARED_TO_LAND:
            return

        text = f"{plane.callsign} RUNWAY {rwy} CLEARED TO LAND"
        self._last_clearance_at[rwy] = time.monotonic()
        self._pending[plane.callsign] = PendingCommand(
            plane.callsign, text, time.monotonic())
        self.sender.send(text)

    def _recheck_finals(self) -> None:
        for plane in self.state.planes.values():
            if plane.phase == Phase.ON_FINAL:
                self._maybe_clear_to_land(plane)
