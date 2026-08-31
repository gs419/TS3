"""Telemetry: track the AI's performance from the event stream.

Subscribe `on_event` alongside the policies. Counts clearances, handoffs,
go-arounds, conflicts, and scoring outcomes, and derives a few rates so you can
see how a session (or a parameter change) actually performed.
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Telemetry:
    counts: Counter = field(default_factory=Counter)
    started: float = field(default_factory=time.monotonic)

    def on_event(self, kind: str, plane) -> None:
        self.counts[kind] += 1
        if kind.startswith("scoring:"):
            self.counts["scoring_total"] += 1
            if any(b in kind for b in ("NEGATIVE", "CRASH", "CLOSE", "SEPARATION",
                                       "UNHANDLED", "FORGOT")):
                self.counts["scoring_negative"] += 1

    def report(self) -> dict:
        mins = max((time.monotonic() - self.started) / 60.0, 1e-9)
        c = self.counts
        landings = c.get("cleared_to_land", 0) + c.get("readback_land", 0)
        return {
            "elapsed_min": round(mins, 1),
            "clearances": {
                "land": c.get("cleared_to_land", 0),
                "runway_reserved": c.get("runway_reserved", 0),
            },
            "handoffs": c.get("handed_off", 0),
            "go_arounds": c.get("go_around", 0),
            "conflicts": c.get("compression", 0),
            "scoring_total": c.get("scoring_total", 0),
            "scoring_negative": c.get("scoring_negative", 0),
            "landings_per_hour": round(landings / mins * 60, 1),
            "raw": dict(c),
        }
