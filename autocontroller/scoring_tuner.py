"""Scoring-driven self-tuning.

Watches the game's `Add Scoring: MSG_*` events and nudges the controllers'
parameters so the AI learns from what costs points — e.g. widen spacing after a
runway-separation hit, add ground margin after a near-collision, enable
auto-handoff after a forgot-departure penalty. Purely reactive and bounded.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Tunables:
    arrival_extra_nm: float = 0.0        # added to wake spacing
    runway_safety_buffer_s: float = 15.0
    ground_conflict_range_m: float = 150.0
    auto_handoff: bool = False
    notes: list = field(default_factory=list)


@dataclass
class ScoringTuner:
    params: Tunables = field(default_factory=Tunables)
    counts: Counter = field(default_factory=Counter)
    # bounds so it can't run away
    max_extra_nm: float = 3.0
    max_buffer_s: float = 45.0
    max_range_m: float = 260.0

    def on_event(self, kind: str, plane) -> None:
        if not kind.startswith("scoring:"):
            return
        msg = kind.split(":", 1)[1]
        self.counts[msg] += 1
        self._react(msg)

    def _react(self, msg: str) -> None:
        p = self.params
        if msg in ("MSG_RUNWAY_SEPARATION", "MSG_RUNWAY_SEPARATION_TIME"):
            p.arrival_extra_nm = min(self.max_extra_nm, p.arrival_extra_nm + 0.5)
            p.runway_safety_buffer_s = min(self.max_buffer_s,
                                           p.runway_safety_buffer_s + 5)
            self._note(f"runway separation → +0.5nm spacing, +5s cross buffer")
        elif msg in ("MSG_AIR_CLOSE", "MSG_CRASH"):
            p.arrival_extra_nm = min(self.max_extra_nm, p.arrival_extra_nm + 1.0)
            self._note("air conflict → +1.0nm arrival spacing")
        elif msg in ("MSG_GROUND_CLOSE", "MSG_GROUND_CRASH"):
            p.ground_conflict_range_m = min(self.max_range_m,
                                            p.ground_conflict_range_m + 40)
            self._note("ground conflict → +40m conflict range")
        elif msg == "MSG_FORGOT_DEPARTURE":
            if not p.auto_handoff:
                p.auto_handoff = True
                self._note("forgot-departure → auto-handoff enabled")

    def _note(self, s: str) -> None:
        self.params.notes.append(s)
        print(f"[tuner] {s}")

    def report(self) -> dict:
        return {"counts": dict(self.counts), "params": self.params}
