"""Parse Tower! Simulator 3 Player.log lines into per-aircraft state.

Line formats are undocumented and build-dependent. The prefixes below follow
TS3CallsignHelper's proven parsers; run a calibration pass on your current
build (see README) and adjust PATTERNS if needed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Optional


class Phase(Enum):
    UNKNOWN = auto()
    ON_FINAL = auto()
    CLEARED_TO_LAND = auto()
    LANDED = auto()
    DEPARTURE = auto()


@dataclass
class Plane:
    callsign: str
    phase: Phase = Phase.UNKNOWN
    runway: Optional[str] = None
    last_transmission: str = ""


@dataclass
class GameState:
    planes: dict[str, Plane] = field(default_factory=dict)
    # runway -> callsign currently holding a landing/takeoff clearance
    runway_reserved_by: dict[str, str] = field(default_factory=dict)

    def plane(self, callsign: str) -> Plane:
        return self.planes.setdefault(callsign, Plane(callsign))


# Regexes for the log lines we care about. \s+ everywhere: the game pads oddly.
PATTERNS = {
    "game_start": re.compile(r"^GAME START"),
    # every command the controller (human or us) issues, echoed by the game
    "command": re.compile(r"^COMMAND:\s+(?P<callsign>\S+)\s+(?P<text>.+)$"),
    # pilot TTS attribution pair: hash line carries the callsign,
    # the following TTS line carries the spoken text
    "tts_hash": re.compile(r"^Gen TTS hash.*?(?P<callsign>\S+)\s*$"),
    "tts_text": re.compile(r"^ADD TTS to \w+:\s+(?P<text>.+)$"),
    "runway_in_cmd": re.compile(r"RUNWAY\s+(?P<runway>[0-9]{1,2}[LRC]?)", re.I),
    "on_final": re.compile(r"\bON\s+FINAL\b.*?RUNWAY\s+(?P<runway>[0-9]{1,2}[LRC]?)|"
                           r"RUNWAY\s+(?P<runway2>[0-9]{1,2}[LRC]?).*?\bON\s+FINAL\b", re.I),
}


class LogInterpreter:
    """Feed raw log lines; emits state changes into GameState and invokes
    `on_event(kind, plane)` callbacks the policy subscribes to."""

    def __init__(self, state: GameState, on_event: Callable[[str, Plane], None]):
        self.state = state
        self.on_event = on_event
        self._pending_tts_callsign: Optional[str] = None

    def feed(self, line: str) -> None:
        line = line.rstrip("\r\n")

        if PATTERNS["game_start"].match(line):
            self.state.planes.clear()
            self.state.runway_reserved_by.clear()
            return

        m = PATTERNS["command"].match(line)
        if m:
            self._handle_command_echo(m["callsign"], m["text"].upper())
            return

        m = PATTERNS["tts_hash"].match(line)
        if m:
            self._pending_tts_callsign = m["callsign"]
            return

        m = PATTERNS["tts_text"].match(line)
        if m and self._pending_tts_callsign:
            self._handle_transmission(self._pending_tts_callsign, m["text"].upper())
            self._pending_tts_callsign = None

    def _handle_command_echo(self, callsign: str, text: str) -> None:
        plane = self.state.plane(callsign)
        rwy = PATTERNS["runway_in_cmd"].search(text)
        if "CLEARED TO LAND" in text:
            plane.phase = Phase.CLEARED_TO_LAND
            if rwy:
                plane.runway = rwy["runway"].upper()
            if plane.runway:
                self.state.runway_reserved_by[plane.runway] = callsign
            self.on_event("cleared_to_land", plane)
        elif "CLEARED FOR TAKEOFF" in text or "LINE UP" in text:
            if rwy:
                self.state.runway_reserved_by[rwy["runway"].upper()] = callsign
            self.on_event("runway_reserved", plane)
        elif "GO AROUND" in text:
            plane.phase = Phase.ON_FINAL
            self._release_runway(callsign)
            self.on_event("go_around", plane)
        elif "CONTACT DEPARTURE" in text:
            self._release_runway(callsign)
            self.on_event("handed_off", plane)

    def _handle_transmission(self, callsign: str, text: str) -> None:
        plane = self.state.plane(callsign)
        plane.last_transmission = text
        m = PATTERNS["on_final"].search(text)
        if m and plane.phase not in (Phase.CLEARED_TO_LAND,):
            plane.phase = Phase.ON_FINAL
            plane.runway = (m["runway"] or m["runway2"]).upper()
            self.on_event("on_final", plane)
        # pilot readback of our clearance confirms delivery
        elif "CLEARED TO LAND" in text and plane.phase != Phase.CLEARED_TO_LAND:
            plane.phase = Phase.CLEARED_TO_LAND
            self.on_event("readback_land", plane)

    def _release_runway(self, callsign: str) -> None:
        for rwy, cs in list(self.state.runway_reserved_by.items()):
            if cs == callsign:
                del self.state.runway_reserved_by[rwy]
