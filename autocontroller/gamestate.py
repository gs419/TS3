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
    # live geometry from the Communication Port (None until first port update)
    pos: Optional[dict] = None          # {x, y, z} game-local meters
    heading: Optional[float] = None     # deg (rot.y)
    speed: Optional[float] = None       # game speed units
    alt_ft: Optional[float] = None      # y (pos.y) as altitude when airborne
    latlon: Optional[tuple] = None      # (lat, lon) derived via airport center
    state_int: Optional[int] = None     # raw AIRPLANES state enum
    target_runway: Optional[str] = None # trgrw
    updated: float = 0.0                # monotonic time of last port update


@dataclass
class GameState:
    planes: dict[str, Plane] = field(default_factory=dict)
    # runway -> callsign currently holding a landing/takeoff clearance
    runway_reserved_by: dict[str, str] = field(default_factory=dict)
    # normalized spoken phrase -> ICAO callsign, from the game's own
    # "speech airplanes:" dictionary line (authoritative for current traffic)
    speech_map: dict[str, str] = field(default_factory=dict)

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
    # airborne position line: "POS: (x, y, z) ROT: .. ALT: n .. rw: R * CALLSIGN"
    "pos_line": re.compile(r"ALT:\s*(?P<alt>-?\d+).*?\brw:\s*(?P<rw>\w+)\s*\*\s*(?P<callsign>[A-Z0-9]+)"),
    # a runway side letter must be standalone, not the leading letter of the next
    # word — otherwise "RUNWAY 15 CLEARED" parses as "15C".
    "runway_in_cmd": re.compile(r"RUNWAY\s+(?P<num>[0-9]{1,2})(?:\s*(?P<side>[LRC])(?![A-Za-z]))?", re.I),
    # the game logs the live spoken-form dictionary for all current traffic
    "speech_airplanes": re.compile(r"^speech airplanes:\s*(?P<body>.+)$"),
    # pilot on-final call, spoken form: "... <callsign> on final <runway>."
    "pilot_final": re.compile(r"^(?:\w+\s+tower,\s+)?(?P<callsign>.+?)\s+on final\s+(?P<runway>[\w\s]+?)\s*\.?\s*$", re.I),
    # engine trace lines carry the callsign as "... * CALLSIGN => <message>"
    "engine_line": re.compile(r"\*\s*(?P<callsign>[A-Z0-9]+)\s*=>\s*(?P<msg>.+)$"),
    "state_change": re.compile(r"STATE CHANGE from\s+(?P<from>STATE_\w+)\s+to\s+(?P<to>STATE_\w+)"),
    # clearance echo that arrives WITHOUT the "COMMAND:" prefix (seen this build)
    "bare_clearance": re.compile(r"^(?P<callsign>[A-Z0-9]{2,7})\s+(?P<text>(?:RUNWAY\s+[0-9]{1,2}\s?[LRC]?\s+)?CLEARED TO LAND.*)$"),
}

# STATE_LAND means the aircraft is on the runway surface. Leaving STATE_LAND, or
# entering any of these, means the runway is (or is about to be) clear again —
# covers normal rollout/exit, go-arounds, flyaways and fly-overs, none of which
# emit a "GO AROUND"/"CONTACT DEPARTURE" command echo.
RUNWAY_FREEING_STATES = frozenset({
    "STATE_ESCAPE_RUNWAY", "STATE_TO_TERMINAL", "STATE_FLYAWAY",
    "STATE_FLYAROUND", "STATE_FLYOVER", "STATE_GO_AROUND",
})


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
            self.state.speech_map.clear()
            return

        m = PATTERNS["speech_airplanes"].match(line)
        if m:
            self._parse_speech(m["body"])
            return

        m = PATTERNS["spawn"].match(line)
        if m:
            self.state.plane(m["callsign"])           # register roster member
            return

        m = PATTERNS["command"].match(line)
        if m:
            self._handle_command_echo(m["callsign"], m["text"].upper())
            return

        # some clearance echoes arrive without the "COMMAND:" prefix this build
        m = PATTERNS["bare_clearance"].match(line)
        if m:
            self._handle_command_echo(m["callsign"], m["text"].upper())
            return

        # engine trace lines ("... * CS => STATE CHANGE ... / Successful landing")
        # are the authoritative signal that a runway has been vacated.
        m = PATTERNS["engine_line"].search(line)
        if m:
            self._handle_engine(m["callsign"], m["msg"])
            # fall through: airborne POS info may also be on this line

        m = PATTERNS["pilot"].match(line)
        if m:
            self._handle_pilot(m["text"])
            return

        m = PATTERNS["scoring"].match(line)
        if m:
            self.on_event("scoring:" + m["msg"], Plane(m["msg"]))
            return

        m = PATTERNS["pos_line"].search(line)
        if m and int(m["alt"]) > 50:
            plane = self.state.plane(m["callsign"])
            if plane.phase in (Phase.UNKNOWN, Phase.DEPARTURE):
                plane.phase = Phase.DEPARTURE
                self.on_event("airborne", plane)

    @staticmethod
    def _norm_spoken(s: str) -> str:
        s = s.lower().replace(",", " ").replace(".", " ").replace("-", " ")
        return re.sub(r"\s+", " ", s).strip()

    def _parse_speech(self, body: str) -> None:
        """Parse the game's 'speech airplanes:' dictionary into an exact
        spoken-phrase -> ICAO map for the current traffic. Entry layout:
          airline: ICAO;CODE;TELEPHONY; digit-form; grouped-form
          GA:      ICAO;GA;<name>; spoken-form
        A pilot's on-final call is TELEPHONY + grouped/digit form (airline) or
        the GA spoken form, so we register each combination."""
        m = self.state.speech_map
        for entry in body.split("|"):
            f = [p.strip() for p in entry.split(";") if p.strip() != ""]
            if len(f) < 2:
                continue
            icao = f[0]
            if not icao:
                continue
            forms = []
            if f[1] == "GA":
                forms.extend(f[3:] if len(f) > 3 else f[2:])
            else:
                tel = f[2] if len(f) > 2 else ""
                for spoken in f[3:]:
                    forms.append(f"{tel} {spoken}")
                if tel:
                    forms.append(tel)
            for form in forms:
                key = self._norm_spoken(form)
                if key:
                    m[key] = icao

    def _resolve_spoken(self, phrase: str, roster: set) -> Optional[str]:
        """Speech-map first (authoritative), then the heuristic resolver."""
        from callsign_resolver import resolve
        key = self._norm_spoken(phrase)
        if key in self.state.speech_map:
            return self.state.speech_map[key]
        return resolve(phrase, roster) or resolve(phrase)

    def _handle_pilot(self, text: str) -> None:
        """PILOT lines are spoken; detect on-final and departure intents,
        resolving the spoken callsign to ICAO where possible."""
        from callsign_resolver import parse_runway
        roster = set(self.state.planes)
        low = text.lower()

        fm = PATTERNS["pilot_final"].match(text)
        if fm:
            cs = self._resolve_spoken(fm["callsign"], roster)
            if cs:
                plane = self.state.plane(cs)
                if plane.phase != Phase.CLEARED_TO_LAND:
                    plane.phase = Phase.ON_FINAL
                    r = parse_runway(fm["runway"])
                    if r:
                        plane.runway = r
                    self.on_event("on_final", plane)
            return

        # departure intents: "... <callsign> requesting push and start" /
        # "... <callsign> ready to taxi". Callsign is the last spoken chunk.
        intent = None
        if "requesting push" in low or "push and start" in low:
            intent = "req_pushback"
        elif "ready to taxi" in low:
            intent = "req_taxi"
        if intent:
            # spoken callsign is the trailing "<airline> <numbers>" phrase
            cs = self._resolve_spoken(text.split(",")[-1], roster) or \
                self._resolve_trailing(text, roster)
            if cs:
                plane = self.state.plane(cs)
                self.on_event(intent, plane)

    def _resolve_trailing(self, text: str, roster: set) -> Optional[str]:
        toks = text.replace(",", " ").split()
        # try progressively longer trailing phrases to catch "<airline> <nums>"
        for start in range(len(toks) - 1, -1, -1):
            cand = self._resolve_spoken(" ".join(toks[start:]), roster)
            if cand:
                return cand
        return None

    def _handle_command_echo(self, callsign: str, text: str) -> None:
        plane = self.state.plane(callsign)
        rwy = PATTERNS["runway_in_cmd"].search(text)
        rwy_norm = (rwy["num"] + (rwy["side"].upper() if rwy["side"] else "")) if rwy else None
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

    def _handle_engine(self, callsign: str, msg: str) -> None:
        """Engine trace lines drive runway release. A landing aircraft holds the
        runway while in STATE_LAND; the moment it leaves that state (to escape /
        taxi / flyaway) or flies over/around, the surface is free again — none of
        which produce a command echo, so this is the only reliable release."""
        sc = PATTERNS["state_change"].search(msg)
        if sc:
            if sc["from"] == "STATE_LAND" or sc["to"] in RUNWAY_FREEING_STATES:
                self._free_runway_for(callsign)
            return
        if "Successful landing" in msg:
            self._free_runway_for(callsign)

    def _free_runway_for(self, callsign: str) -> None:
        plane = self.state.plane(callsign)
        plane.phase = Phase.LANDED
        if self._release_runway(callsign):
            self.on_event("runway_cleared", plane)

    def _release_runway(self, callsign: str) -> bool:
        freed = False
        for rwy, cs in list(self.state.runway_reserved_by.items()):
            if cs == callsign:
                del self.state.runway_reserved_by[rwy]
                freed = True
        return freed
