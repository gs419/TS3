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
    # current build (v1.5.x, MeloTTS): calibrated against real Player.log
    "command": re.compile(r"^COMMAND:\s+(?P<callsign>[A-Z0-9]+)\s+(?P<text>.+)$"),
    "spawn": re.compile(r"^CREATE SERVER AIRPLANE:\s+(?P<callsign>[A-Z0-9]+)"),
    "set_plane": re.compile(r"^SET PlANE:\s+(?P<callsign>[A-Z0-9]+)"),
    "pilot": re.compile(r"^PILOT:\s+(?P<text>.+)$"),
    "scoring": re.compile(r"^Add Scoring:\s+(?P<msg>MSG_\w+)"),
    "runway_in_cmd": re.compile(r"RUNWAY\s+(?P<runway>[0-9]{1,2}\s?[LRC]?)", re.I),
    # pilot on-final call, spoken form: "... <callsign> on final <runway>."
    "pilot_final": re.compile(r"^(?:\w+\s+tower,\s+)?(?P<callsign>.+?)\s+on final\s+(?P<runway>[\w\s]+?)\s*\.?\s*$", re.I),
}


class LogInterpreter:
    """Feed raw log lines; emits state changes into GameState and invokes
    `on_event(kind, plane)` callbacks the policy subscribes to."""

    def __init__(self, state: GameState, on_event: Callable[[str, Plane], None]):
        self.state = state
        self.on_event = on_event

    def feed(self, line: str) -> None:
        line = line.rstrip("\r\n")

        if PATTERNS["game_start"].match(line):
            self.state.planes.clear()
            self.state.runway_reserved_by.clear()
            return

        m = PATTERNS["spawn"].match(line)
        if m:
            self.state.plane(m["callsign"])           # register roster member
            return

        m = PATTERNS["command"].match(line)
        if m:
            self._handle_command_echo(m["callsign"], m["text"].upper())
            return

        m = PATTERNS["pilot"].match(line)
        if m:
            self._handle_pilot(m["text"])
            return

        m = PATTERNS["scoring"].match(line)
        if m:
            self.on_event("scoring:" + m["msg"], Plane(m["msg"]))
            return

    def _handle_pilot(self, text: str) -> None:
        """PILOT lines are spoken; detect on-final and resolve to ICAO."""
        fm = PATTERNS["pilot_final"].match(text)
        if not fm:
            return
        # lazy import to keep gamestate importable standalone
        from callsign_resolver import resolve, parse_runway
        roster = set(self.state.planes)
        cs = resolve(fm["callsign"], roster) or resolve(fm["callsign"])
        rwy = parse_runway(fm["runway"])
        if not cs:
            return
        plane = self.state.plane(cs)
        if plane.phase != Phase.CLEARED_TO_LAND:
            plane.phase = Phase.ON_FINAL
            if rwy:
                plane.runway = rwy
            self.on_event("on_final", plane)

    def _handle_command_echo(self, callsign: str, text: str) -> None:
        plane = self.state.plane(callsign)
        rwy = PATTERNS["runway_in_cmd"].search(text)
        rwy_norm = rwy["runway"].upper().replace(" ", "") if rwy else None
        if "CLEARED TO LAND" in text:
            plane.phase = Phase.CLEARED_TO_LAND
            if rwy_norm:
                plane.runway = rwy_norm
                self.state.runway_reserved_by[rwy_norm] = callsign
            self.on_event("cleared_to_land", plane)
        elif "CLEARED FOR TAKEOFF" in text or "LINE UP" in text:
            if rwy_norm:
                self.state.runway_reserved_by[rwy_norm] = callsign
            self.on_event("runway_reserved", plane)
        elif "GO AROUND" in text:
            plane.phase = Phase.ON_FINAL
            self._release_runway(callsign)
            self.on_event("go_around", plane)
        elif "CONTACT DEPARTURE" in text:
            self._release_runway(callsign)
            self.on_event("handed_off", plane)

    def _release_runway(self, callsign: str) -> None:
        for rwy, cs in list(self.state.runway_reserved_by.items()):
            if cs == callsign:
                del self.state.runway_reserved_by[rwy]
