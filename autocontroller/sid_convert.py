"""Convert departure-procedure data into sids.json (departures.py schema).

Two inputs:
  - an intermediate CSV (practical, testable now): columns
    airport,runway,sid,dest,initial_climb_ft,turn,heading[,seq,leg_heading,leg_climb]
  - FAA CIFP / ARINC 424 (real source): parse SID leg records. ARINC 424 is
    fixed-width and involved; use a dedicated parser (e.g. the `arinc424`
    package) to emit the intermediate CSV, then run csv_to_sids. This module
    ships the CSV path fully and a documented stub for the ARINC path.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict


def csv_to_sids(csv_path: str) -> dict:
    """Build the sids.json structure from the intermediate CSV."""
    airports = defaultdict(lambda: {"runways": {}})
    legs = defaultdict(list)   # (airport,runway,sid) -> [(seq,heading,climb)]
    rows = []
    with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            rows.append(row)
            if row.get("leg_heading") or row.get("leg_climb"):
                legs[(row["airport"], row["runway"], row.get("sid", ""))].append(
                    (int(row.get("seq", 0) or 0),
                     _int(row.get("leg_heading")), _int(row.get("leg_climb"))))
    for row in rows:
        ap, rw = row["airport"].upper(), row["runway"].upper()
        entry = {
            "sid": row.get("sid", ""),
            "initial_climb_ft": _int(row.get("initial_climb_ft")) or 3000,
        }
        turn = (row.get("turn") or "").strip().upper()
        if turn in ("LEFT", "RIGHT"):
            entry["turn_on_course"] = turn
        if row.get("heading"):
            entry["initial_heading"] = _int(row["heading"])
        lg = sorted(legs.get((row["airport"], rw, row.get("sid", "")), []))
        if lg:
            entry["legs"] = [{"heading": h, "climb_ft": c}
                             for _, h, c in lg if h or c]
        rwys = airports[ap]["runways"].setdefault(rw, {})
        if row.get("dest"):
            rwys.setdefault("by_dest", {})[row["dest"].upper()] = entry
        else:
            rwys["default"] = entry
    return dict(airports)


def convert(csv_path: str, out_path: str) -> dict:
    data = csv_to_sids(csv_path)
    json.dump(data, open(out_path, "w"), indent=2)
    return data


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


# ARINC 424 path (documented stub):
def arinc424_to_csv(*_a, **_k):
    raise NotImplementedError(
        "Parse FAA CIFP with an ARINC-424 library into the intermediate CSV "
        "(airport,runway,sid,dest,initial_climb_ft,turn,heading,seq,leg_heading,"
        "leg_climb), then call csv_to_sids. See module docstring.")
