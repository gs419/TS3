"""Decision rules: the 'AI controller'. Basic version: clear arrivals to land.

Deliberately conservative — one outstanding landing clearance per runway,
cooldown between clearances, retry once if the game never echoes our command.
Once a runway's holder lands and vacates the surface (gamestate emits
`runway_cleared`), the next aircraft on final becomes clearable.
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
    # aircraft we issued to but the game never confirmed after retries: hand to
    # the human and stop re-nagging (also frees the runway cooldown for the next
    # arrival). Cleared if the game later echoes a clearance for them.
    _abandoned: set = field(default_factory=set)
    _last_note: dict[str, str] = field(default_factory=dict)

    # ---- event hooks from LogInterpreter ------------------------------
    def on_event(self, kind: str, plane: Plane) -> None:
        if kind == "on_final":
            self._maybe_clear_to_land(plane)
        elif kind in ("cleared_to_land", "readback_land"):
            # our command was echoed / read back: done, and no longer abandoned
            self._pending.pop(plane.callsign, None)
            self._abandoned.discard(plane.callsign)
        elif kind in ("go_around", "runway_cleared"):
            # runway freed (go-around, or the previous arrival vacated the
            # surface): a queued arrival on final may now be clearable
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
                    self._abandoned.add(cs)
        # opportunistically re-check finals: covers arrivals that were blocked
        # by a now-freed runway or by a cooldown that has since expired.
        self._recheck_finals()

    # ---- rules --------------------------------------------------------
    def _note(self, callsign: str, msg: str) -> None:
        """Print a status line only when it changes, to avoid per-tick spam."""
        if self._last_note.get(callsign) != msg:
            self._last_note[callsign] = msg
            print(msg)

    def _maybe_clear_to_land(self, plane: Plane) -> None:
        if not self.enabled or not plane.runway:
            return
        if plane.callsign in self._abandoned:
            return
        rwy = plane.runway
        holder = self.state.runway_reserved_by.get(rwy)
        if holder and holder != plane.callsign:
            self._note(plane.callsign,
                       f"[policy] {plane.callsign} on final {rwy}, but {holder} "
                       f"holds the runway — waiting")
            return
        last = self._last_clearance_at.get(rwy, 0.0)
        if time.monotonic() - last < self.runway_cooldown_s:
            self._note(plane.callsign,
                       f"[policy] {plane.callsign} on final {rwy} — cooldown, waiting")
            return
        if plane.callsign in self._pending or plane.phase == Phase.CLEARED_TO_LAND:
            return

        text = f"{plane.callsign} RUNWAY {rwy} CLEARED TO LAND"
        self._last_clearance_at[rwy] = time.monotonic()
        self._pending[plane.callsign] = PendingCommand(
            plane.callsign, text, time.monotonic())
        self._last_note.pop(plane.callsign, None)
        self.sender.send(text)

    def _recheck_finals(self) -> None:
        for plane in self.state.planes.values():
            if plane.phase == Phase.ON_FINAL:
                self._maybe_clear_to_land(plane)
