"""Per-position voices, phrasing variety, and readback checking.

The port's TTS SAY channel takes a `voice_id`, so each controller position can
sound distinct (Sally vs Bob). Also small phrasing variety so the AI doesn't
sound robotic, and a readback checker for a training mode.
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field


@dataclass
class VoiceBook:
    by_position: dict = field(default_factory=dict)   # position name -> voice_id
    default: int = 7

    def voice_for(self, position: str) -> int:
        return self.by_position.get(position, self.default)

    def say(self, position: str, text: str, speed: float = 1.1) -> dict:
        """Build a TTS SAY command (matches the decoded port format)."""
        return {"cmd": {"type": "SAY", "params": {
            "voice_id": self.voice_for(position), "quality": 0,
            "speed": speed, "text": text}}}


# light phrasing variety — same meaning, varied wording
_VARIANTS = {
    "cleared to land": ["cleared to land", "cleared to land", "you're cleared to land"],
    "line up and wait": ["line up and wait", "line up and wait"],
    "contact departure": ["contact departure", "contact departure now"],
    "roger": ["roger", "roger that", "copy"],
}


def vary(phrase: str, rng: random.Random | None = None) -> str:
    rng = rng or random
    key = phrase.lower()
    return rng.choice(_VARIANTS.get(key, [phrase]))


def readback_ok(issued: str, readback: str) -> tuple:
    """Compare a pilot readback against the issued clearance on the safety-
    critical tokens (runway, hold-short, altitude). Returns (ok, missing)."""
    def toks(s):
        s = s.upper()
        out = set()
        for m in re.finditer(r"RUNWAY\s+(\d{1,2}[LRC]?)", s):
            out.add(("RWY", m.group(1)))
        if "HOLD SHORT" in s:
            out.add(("HOLDSHORT", True))
        for m in re.finditer(r"(?:ALTITUDE|CLIMB TO)\s+(\d{3,5})", s):
            out.add(("ALT", m.group(1)))
        for kw in ("CLEARED TO LAND", "CLEARED FOR TAKEOFF", "GO AROUND",
                   "CONTACT DEPARTURE", "CROSS"):
            if kw in s:
                out.add(("ACT", kw))
        return out
    want = toks(issued)
    missing = want - toks(readback)
    return (len(missing) == 0), sorted(missing)
