"""Spacing/compression advisor — consumes the WorldModel 'compression' event.

Honest about the sim's levers: the tower has no speed-assignment command, so on
an IFR final the real options are to speed the LEADER (MAKE SHORT APPROACH) or
send the TRAILER around (GO AROUND). VFR/pattern traffic additionally allows
MAKE 360 / EXTEND. Defaults to ADVISE (print) rather than auto-issuing a
go-around, since a go-around is disruptive.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from gamestate import GameState, Plane


@dataclass
class SpacingAdvisor:
    state: GameState
    sender: object
    auto: bool = False          # False = advise only; True = auto go-around
    cooldown_s: float = 20.0
    _last: dict = field(default_factory=dict)

    def on_event(self, kind: str, plane: Plane) -> None:
        if kind != "compression":
            return
        cs = plane.callsign
        if time.monotonic() - self._last.get(cs, 0) < self.cooldown_s:
            return
        self._last[cs] = time.monotonic()
        detail = plane.last_transmission  # "COMPRESSION x.xnm behind YYY"
        if self.auto:
            self.sender.send(f"{cs} GO AROUND")
        else:
            print(f"[spacing] ADVISORY: {cs} {detail} — consider GO AROUND ({cs}) "
                  f"or MAKE SHORT APPROACH (leader)")
