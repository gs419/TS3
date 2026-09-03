"""PositionManager: tracks which controller owns each aircraft and performs
handoffs along a configured chain.

Consumes semantic events (from the WorldModel / log): landed_on:<rwy>,
exited_runway, holding_short:<rwy>, crossed:<rwy>, reached:<area>. On a matching
handoff it transfers ownership and:
  - CONTACT <freq>  if the next position is on a different frequency,
  - virtual (silent) if same frequency (e.g. splitting one tower freq),
  - stand-down + human alert if the next position is the human.

Each AI position delegates the actual control to a scoped controller policy
(arrival/ground/ramp); this class only owns the routing/handoff fabric.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from positions import PositionMap, Position


@dataclass
class Ownership:
    callsign: str
    position: str          # current owning position name
    since_event: str = ""


@dataclass
class PositionManager:
    pmap: PositionMap
    sender: object                                   # .send(text)
    notify_human: Callable[[str, str], None] = lambda cs, msg: print(f"[HUMAN] {cs}: {msg}")
    on_assign: Callable[[str, Optional[Position]], None] = lambda cs, pos: None
    owner: dict = field(default_factory=dict)        # callsign -> Ownership
    # role -> CONTACT wording (see contact_phrase); None = built-in table
    contact_phrases: Optional[dict] = None

    # ---- initial assignment ------------------------------------------
    def assign_initial(self, callsign: str, *, runway=None, area=None) -> Optional[Position]:
        pos = self.pmap.responsible_for(runway=runway, area=area)
        if pos:
            self.owner[callsign] = Ownership(callsign, pos.name, "initial")
            self.on_assign(callsign, pos)
        return pos

    def current(self, callsign: str) -> Optional[Position]:
        o = self.owner.get(callsign)
        return self.pmap.position(o.position) if o else None

    # ---- event-driven handoff ----------------------------------------
    def handle_event(self, event_key: str, callsign: str) -> Optional[str]:
        """Feed a semantic event; performs a handoff if the chain calls for it.
        Returns a short description of what happened, or None."""
        cur = self.owner.get(callsign)
        frm = cur.position if cur else None
        h = self.pmap.handoff_for(event_key, frm)
        if not h:
            return None
        src = self.pmap.position(frm) if frm else None
        dst = self.pmap.position(h.to) if h.to else None

        if dst is None:
            # leaves the airport (parked at ramp / departed)
            self.owner.pop(callsign, None)
            self.on_assign(callsign, None)
            return f"{callsign}: {frm or '?'} -> (complete)"

        self.owner[callsign] = Ownership(callsign, dst.name, event_key)
        self.on_assign(callsign, dst)

        # decide the mechanism
        if dst.kind == "human":
            self.notify_human(callsign,
                              f"handoff from {src.name if src else '?'} — now on your "
                              f"{dst.role} ({dst.frequency})")
            return f"{callsign}: {frm} -> {dst.name} (HUMAN alert)"
        # AI target
        if src and src.frequency and dst.frequency and src.frequency != dst.frequency:
            # cross-frequency: real CONTACT command from the source controller
            phrase = self.contact_phrase(dst)
            self.sender.send(f"{callsign} {phrase}")
            return f"{callsign}: {frm} -> {dst.name} ({phrase})"
        # same frequency: virtual transfer, no game command
        return f"{callsign}: {frm} -> {dst.name} (virtual)"

    # role -> the CONTACT wording the game's grammar accepts. "CONTACT
    # DEPARTURE" is confirmed in-game; the others follow the same pattern.
    # Override with `contact_phrases` if a build wants the frequency spoken.
    def contact_phrase(self, dst: Position) -> str:
        table = self.contact_phrases or {
            "ground": "CONTACT GROUND", "ramp": "CONTACT RAMP",
            "departure": "CONTACT DEPARTURE", "local": "CONTACT TOWER",
            "clearance": "CONTACT CLEARANCE",
        }
        return table.get(dst.role, f"CONTACT {dst.frequency}")

    # ---- convenience: build semantic events from world/log -----------
    @staticmethod
    def event_landed(runway: str) -> str: return f"landed_on:{runway}"
    @staticmethod
    def event_holding_short(runway: str) -> str: return f"holding_short:{runway}"
    @staticmethod
    def event_crossed(runway: str) -> str: return f"crossed:{runway}"
    @staticmethod
    def event_reached(area: str) -> str: return f"reached:{area}"
