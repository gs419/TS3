"""Regression harness: replay a Player.log through the pipeline and assert.

Formalizes the ad-hoc replay tests. Feed a recorded log and a list of
expectations; get a pass/fail report. Use it to guard the policies on every
change (run against your saved session logs).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from gamestate import GameState, LogInterpreter


@dataclass
class Expect:
    kind: str            # event kind, e.g. "on_final", "cleared_to_land", "scoring:MSG_LANDING_SUCCESSFUL"
    min_count: int = 1
    callsign: str = ""   # optional: require this callsign


@dataclass
class Result:
    passed: bool
    detail: str


def replay(log_path: str, expectations: list) -> list:
    state = GameState()
    seen = []
    interp = LogInterpreter(state, lambda k, p: seen.append((k, p.callsign)))
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            interp.feed(line)
    results = []
    for e in expectations:
        hits = [cs for (k, cs) in seen
                if k == e.kind and (not e.callsign or cs == e.callsign)]
        ok = len(hits) >= e.min_count
        results.append(Result(ok, f"{e.kind}"
                              f"{'/'+e.callsign if e.callsign else ''}: "
                              f"{len(hits)} (need {e.min_count}) "
                              f"{'PASS' if ok else 'FAIL'}"))
    return results


def run(log_path: str, expectations: list) -> bool:
    results = replay(log_path, expectations)
    for r in results:
        print(("  ok " if r.passed else "  XX ") + r.detail)
    return all(r.passed for r in results)
