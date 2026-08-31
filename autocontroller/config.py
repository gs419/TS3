"""Unified runtime config for the AI-ATC engine.

One place for the parameters the policies + arbiter + safety checks read, plus
`apply_tunables()` so the scoring tuner's learned adjustments feed back into the
live params.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict


@dataclass
class Config:
    airport_icao: str = ""
    default_runway: str = ""
    candidate_runways: tuple = ()
    magvar_deg: float = 0.0
    speed_to_mps: float = 1.0
    # arrival / spacing
    runway_cooldown_s: float = 25.0
    arrival_extra_nm: float = 0.0
    # runway-cross safety
    cross_clear_s: float = 30.0
    safety_buffer_s: float = 15.0
    # ground
    ground_conflict_range_m: float = 150.0
    # arbiter
    aircraft_cooldown_s: float = 8.0
    arbiter_runway_cooldown_s: float = 12.0
    # behaviour
    auto_handoff: bool = False
    dry_run: bool = True

    def apply_tunables(self, t) -> None:
        """Fold scoring-tuner adjustments into live params."""
        self.arrival_extra_nm = t.arrival_extra_nm
        self.safety_buffer_s = t.runway_safety_buffer_s
        self.ground_conflict_range_m = t.ground_conflict_range_m
        self.auto_handoff = t.auto_handoff

    @classmethod
    def load(cls, path: str) -> "Config":
        return cls(**json.load(open(path, encoding="utf-8")))

    def save(self, path: str) -> None:
        json.dump(asdict(self), open(path, "w"), indent=2)
