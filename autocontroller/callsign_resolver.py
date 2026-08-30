"""Resolve a spoken callsign (from a PILOT: log line) to an ICAO callsign,
disambiguated against the known plane roster.

Current-build logs phrase pilot calls in spoken form
("southwest ten sixty-five", "delta sixty-nine zero five heavy"), while
COMMAND: lines and the port use ICAO codes (SWA1065, DAL6905). This bridges
the two so a log-only auto-controller can act on "on final" calls.

The airline map is seeded from what appears in sample logs; extend it from the
game's Airports/*/databases/*/airlines.csv (telephony -> ICAO).
"""
from __future__ import annotations
import re

# spoken telephony -> ICAO prefix (extend from airlines.csv)
AIRLINES = {
    "southwest": "SWA", "delta": "DAL", "sky west": "SKW", "skywest": "SKW",
    "avelo": "VXP", "jetblue": "JBU", "american": "AAL", "united": "UAL",
    "frontier": "FFT", "spirit": "NKS", "alaska": "ASA", "endeavor": "EDV",
    "republic": "RPA", "jsx": "JSX",
}
_UNITS = {"zero":0,"one":1,"two":2,"three":3,"four":4,"five":5,"six":6,
          "seven":7,"eight":8,"nyner":9,"niner":9,"nine":9}
_TEENS = {"ten":10,"eleven":11,"twelve":12,"thirteen":13,"fourteen":14,
          "fifteen":15,"sixteen":16,"seventeen":17,"eighteen":18,"nineteen":19}
_TENS = {"twenty":20,"thirty":30,"fourty":40,"forty":40,"fifty":50,"sixty":60,
         "seventy":70,"eighty":80,"ninety":90}
_STRIP = {"heavy","super","tower","ground","and","start","on","final","with",
          "information","requesting","push","ready","to","taxi","for","landing"}


def _spoken_numbers_to_digits(tokens: list[str]) -> str:
    """Turn a run of number-words into a digit string, grouping like ATC does
    ('sixty two'->'62', 'zero five'->'05', 'ten'->'10', 'thirty'->'30')."""
    out = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in _TENS:
            if i+1 < len(tokens) and tokens[i+1] in _UNITS and tokens[i+1] != "zero":
                out.append(str(_TENS[t] + _UNITS[tokens[i+1]])); i += 2
            else:
                out.append(str(_TENS[t])); i += 1
        elif t in _TEENS:
            out.append(str(_TEENS[t])); i += 1
        elif t in _UNITS:
            # 'zero five' -> '05'; lone digit -> its value
            if t == "zero" and i+1 < len(tokens) and tokens[i+1] in _UNITS:
                out.append(f"0{_UNITS[tokens[i+1]]}"); i += 2
            else:
                out.append(str(_UNITS[t])); i += 1
        else:
            i += 1
    return "".join(out)


def resolve(spoken: str, roster: set[str] | None = None) -> str | None:
    """Best-effort ICAO callsign from a spoken fragment.
    If `roster` is given, the result is only returned when it matches a known
    plane (which disambiguates grouping)."""
    s = spoken.lower().replace(",", " ").replace(".", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    # airline prefix: try two-word names first
    icao = None
    rest = s
    for name in sorted(AIRLINES, key=lambda n: -len(n)):
        if s.startswith(name + " ") or s == name:
            icao = AIRLINES[name]; rest = s[len(name):].strip(); break
    if not icao:
        return None
    toks = [t for t in rest.split() if t not in _STRIP]
    # stop at the first non-number token run
    numtoks = []
    for t in toks:
        if t in _UNITS or t in _TEENS or t in _TENS:
            numtoks.append(t)
        elif numtoks:
            break
    digits = _spoken_numbers_to_digits(numtoks)
    cand = f"{icao}{digits}"
    if roster is None:
        return cand
    if cand in roster:
        return cand
    # tolerate leading-zero / grouping differences: match on prefix+int
    try:
        want = int(digits)
    except ValueError:
        return None
    for r in roster:
        if r.startswith(icao) and r[len(icao):].isdigit() and int(r[len(icao):]) == want:
            return r
    return None


ONFINAL_RE = re.compile(r"on final\s+(?P<rwy>[\w\s]+?)\s*$", re.I)
_RWYNUM = {**{k:str(v) for k,v in _UNITS.items()}, **{k:str(v) for k,v in _TEENS.items()},
           **{k:str(v) for k,v in _TENS.items()}}

def parse_runway(spoken_rwy: str) -> str | None:
    """'two seven left' -> '27L', 'one five' -> '15'."""
    toks = spoken_rwy.lower().split()
    side = ""
    digs = []
    for t in toks:
        if t in ("left",): side = "L"
        elif t in ("right",): side = "R"
        elif t in ("center","centre"): side = "C"
        elif t in _RWYNUM: digs.append(_RWYNUM[t])
    return ("".join(digs) + side) if digs else None
