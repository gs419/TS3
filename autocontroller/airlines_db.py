"""Load the airport's airlines.csv into the callsign resolver's telephony map.

The resolver ships a small hand-seeded airline→ICAO map; this expands it to the
full table from the game's `Airports/*/databases/*/airlines.csv`. Column names
vary, so we detect an ICAO/code column and a telephony/callsign column.
"""
from __future__ import annotations

import csv


def load_airlines(path: str) -> dict:
    """Return {telephony_lower: ICAO}. Detects columns heuristically."""
    out = {}
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            keys = {k.lower(): k for k in row}
            icao = next((row[keys[k]] for k in keys
                         if k in ("icao", "code", "al", "airline") and
                         len(str(row[keys[k]]).strip()) == 3), None)
            tel = next((row[keys[k]] for k in keys
                        if "callsign" in k or "telephony" in k or "say" in k
                        or "name" in k), None)
            if icao and tel:
                out[tel.strip().lower()] = icao.strip().upper()
    return out


def install(path: str) -> int:
    """Merge airlines.csv telephony map into callsign_resolver.AIRLINES.
    Returns the number of entries added."""
    import callsign_resolver as cr
    mapping = load_airlines(path)
    before = len(cr.AIRLINES)
    cr.AIRLINES.update(mapping)
    return len(cr.AIRLINES) - before
