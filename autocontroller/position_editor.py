#!/usr/bin/env python3
"""position_editor.py -- a small local web GUI for autocontroller/positions.json.

Pick an airport, say which controller (a named AI or the Human) works each
position, and assign every runway / area to exactly one position. Reads and
writes the real ``positions.json`` (see positions.py for the schema).

Run:
    python position_editor.py [--port 8765] [--file <positions.json>] [--no-browser]

Endpoints (bound to 127.0.0.1 only):
    GET  /                      the editor page (embedded below, works offline)
    GET  /api/config            the current positions.json document
    POST /api/config            full JSON document -> normalised, validated, written atomically
                                -> {"ok": true, "path": ...} or {"ok": false, "error": ...} with
                                400 invalid document / 403 cross-site request / 409 the file on
                                disk exists but cannot be parsed (never overwritten) / 415 body
                                is not application/json
    GET  /api/runways?icao=XXXX best-effort runway designators from testdata/<icao>_airport.json
    GET  /api/areas?icao=XXXX   best-effort area names (Terminal<X> from gate names)
    GET  /api/meta              {"file": ..., "exists": ...}

Standard library only (http.server / json / argparse / webbrowser / pathlib / os / sys).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROLES = ("local", "ground", "ramp", "departure", "clearance")
KINDS = ("ai", "human")

DEFAULT_COMMENT = (
    "Multi-position layout per airport. role: local|ground|ramp|departure|clearance. "
    "kind: ai|human. owns_runways / owns_areas define each position's authority. "
    "handoffs: when an event fires, ownership moves from 'from' (optional) to 'to' "
    "(null = leaves the airport). Frequencies are placeholders; align to the airport's "
    "real freqs or a custom multi-freq airport package."
)

MAX_BODY = 8 * 1024 * 1024


# --------------------------------------------------------------------------
# config file helpers
# --------------------------------------------------------------------------
def default_config_path() -> Path:
    return Path(__file__).resolve().parent / "positions.json"


class UnreadableConfigError(Exception):
    """The target file exists but cannot be parsed. Writing over it would destroy
    whatever the user has in there, so a save must be refused, not treated as
    'the file is empty'."""


def load_config(path: Path) -> dict:
    """Load the document. A missing file -- or an existing but blank one (0 bytes /
    whitespace only, e.g. a fresh 'New text document') -- yields an empty skeleton
    (comment only); there is nothing in it to protect. Anything else that cannot be
    parsed raises, and callers must never treat that as an empty document.
    Read as utf-8-sig so a Windows UTF-8 BOM (PowerShell 5 Set-Content -Encoding
    UTF8, Notepad 'UTF-8 with BOM') does not make the file unreadable."""
    if not path.exists():
        return {"_comment": DEFAULT_COMMENT}
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return {"_comment": DEFAULT_COMMENT}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("positions file must contain a JSON object at the top level")
    return data


def _is_str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)


def normalize_config(doc) -> None:
    """Trim whitespace around the identifiers that positions.py matches by exact
    string comparison: position names, runway / area designators, handoff event
    keys and position references. Nothing else is touched (unknown fields stay,
    types are not coerced -- validate_config reports those). Mirrors normalizeDoc()
    in the page, so 'Bob ' and 'Bob' can never become two positions on disk."""
    if not isinstance(doc, dict):
        return
    for icao, entry in doc.items():
        if icao.startswith("_") or not isinstance(entry, dict):
            continue
        positions = entry.get("positions")
        for p in positions if isinstance(positions, list) else []:
            if not isinstance(p, dict):
                continue
            if isinstance(p.get("name"), str):
                p["name"] = p["name"].strip()
            for key in ("owns_runways", "owns_areas"):
                if isinstance(p.get(key), list):
                    p[key] = [x.strip() if isinstance(x, str) else x for x in p[key]]
        handoffs = entry.get("handoffs")
        for h in handoffs if isinstance(handoffs, list) else []:
            if not isinstance(h, dict):
                continue
            for key in ("when", "from", "to"):
                if isinstance(h.get(key), str):
                    h[key] = h[key].strip()


def validate_config(doc) -> None:
    """Raise ValueError (with a human-readable message) if ``doc`` is not a valid
    positions document. Keys starting with '_' are metadata and are skipped; every
    other top-level key is an airport entry -- positions.py looks entries up by
    ICAO and crashes on anything but an object -- so it must be an object with a
    'positions' list. Also enforces what the consumer silently relies on: unique
    (trimmed) names, at most one owner per runway, and handoffs that reference
    positions which exist at that airport."""
    if not isinstance(doc, dict):
        raise ValueError("top level must be a JSON object")
    for icao, entry in doc.items():
        if icao.startswith("_"):
            continue
        where = f"airport {icao}"
        if not isinstance(entry, dict):
            raise ValueError(f"top-level key '{icao}' must be an airport object with a 'positions' list "
                             f"(got {type(entry).__name__}); metadata keys must start with '_'")
        positions = entry.get("positions")
        if not isinstance(positions, list):
            raise ValueError(f"{where}: 'positions' must be a list")
        names = set()
        runway_owner: dict = {}          # runway -> name of the position that owns it
        for i, p in enumerate(positions):
            pw = f"{where}, position #{i + 1}"
            if not isinstance(p, dict):
                raise ValueError(f"{pw}: must be an object")
            name = p.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"{pw}: 'name' must be a non-empty string")
            name = name.strip()          # same comparison the page makes
            if name in names:
                raise ValueError(f"{where}: duplicate position name '{name}'")
            names.add(name)
            pw = f"{where}, position '{name}'"
            role = p.get("role")
            if role not in ROLES:
                raise ValueError(f"{pw}: role must be one of {', '.join(ROLES)} (got {role!r})")
            kind = p.get("kind", "ai")
            if kind not in KINDS:
                raise ValueError(f"{pw}: kind must be 'ai' or 'human' (got {kind!r})")
            if "frequency" in p and not isinstance(p["frequency"], str):
                raise ValueError(f"{pw}: 'frequency' must be a string, e.g. \"118.7\"")
            for key in ("owns_runways", "owns_areas"):
                if key in p and not _is_str_list(p[key]):
                    raise ValueError(f"{pw}: '{key}' must be a list of non-empty strings")
            for rwy in p.get("owns_runways") or []:
                owner = runway_owner.setdefault(rwy.strip(), name)
                if owner != name:
                    raise ValueError(f"{where}: runway '{rwy.strip()}' is owned by both '{owner}' and '{name}' "
                                     "-- a runway can have only one owner")
        handoffs = entry.get("handoffs", [])
        if not isinstance(handoffs, list):
            raise ValueError(f"{where}: 'handoffs' must be a list")
        for j, h in enumerate(handoffs):
            hw = f"{where}, handoff #{j + 1}"
            if not isinstance(h, dict):
                raise ValueError(f"{hw}: must be an object")
            when = h.get("when")
            if not isinstance(when, str) or not when.strip():
                raise ValueError(f"{hw}: 'when' must be a non-empty string (e.g. landed_on:24R)")
            if "to" not in h:
                raise ValueError(f"{hw} ({when}): missing 'to' (use null for 'leaves the airport')")
            for key in ("from", "to"):
                ref = h.get(key)
                if ref is None:
                    continue
                if not isinstance(ref, str) or not ref.strip():
                    raise ValueError(f"{hw} ({when}): '{key}' must be a position name or null")
                if ref.strip() not in names:
                    raise ValueError(f"{hw} ({when}): '{key}' refers to unknown position '{ref}' "
                                     f"(positions at {icao}: {', '.join(sorted(names)) or 'none'})")


def _inline(v) -> str:
    """One-line JSON with ', ' / ': ' separators (mirrors the editor's preview)."""
    return json.dumps(v, ensure_ascii=False)


def dumps_config(doc: dict) -> str:
    """Pretty-print in the same shape as the hand-written file: airports indented,
    one position / handoff per line. Anything unexpected falls back to indent=2."""
    lines = ["{"]
    items = list(doc.items())
    for i, (k, v) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        if isinstance(v, dict) and isinstance(v.get("positions"), list):
            lines.append(f"  {_inline(k)}: {{")
            sub = list(v.items())
            for j, (sk, sv) in enumerate(sub):
                scomma = "," if j < len(sub) - 1 else ""
                if (sk in ("positions", "handoffs") and isinstance(sv, list)
                        and all(isinstance(x, dict) for x in sv)):
                    if not sv:
                        lines.append(f"    {_inline(sk)}: []{scomma}")
                    else:
                        lines.append(f"    {_inline(sk)}: [")
                        for n, x in enumerate(sv):
                            xcomma = "," if n < len(sv) - 1 else ""
                            lines.append(f"      {_inline(x)}{xcomma}")
                        lines.append(f"    ]{scomma}")
                else:
                    body = json.dumps(sv, ensure_ascii=False, indent=2).replace("\n", "\n    ")
                    lines.append(f"    {_inline(sk)}: {body}{scomma}")
            lines.append(f"  }}{comma}")
        else:
            body = json.dumps(v, ensure_ascii=False, indent=2).replace("\n", "\n  ")
            lines.append(f"  {_inline(k)}: {body}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def merge_with_disk(path: Path, posted: dict) -> dict:
    """The posted document is authoritative for airports; '_'-prefixed metadata
    keys that exist on disk but were not posted are carried over. '_comment'
    stays first. A file that exists but cannot be parsed raises
    UnreadableConfigError: it must not be mistaken for an empty document and
    then overwritten with the posted one."""
    if path.exists():
        try:
            current = load_config(path)
        except Exception as e:
            raise UnreadableConfigError(
                f"refusing to overwrite an unreadable file: {path}: {e}. "
                "Fix the JSON (or move the file away) and try again.") from e
    else:
        current = {}
    out: dict = {}
    if "_comment" in posted:
        out["_comment"] = posted["_comment"]
    elif "_comment" in current:
        out["_comment"] = current["_comment"]
    for k, v in posted.items():
        if k not in out:
            out[k] = v
    for k, v in current.items():
        if k.startswith("_") and k not in out:
            out[k] = v
    return out


def save_config_atomic(path: Path, doc: dict) -> None:
    """Write to a sibling temp file, fsync, then os.replace over the target."""
    text = dumps_config(doc)
    if json.loads(text) != doc:            # self-check: what we write parses back identically
        raise ValueError("internal error: serialised document does not round-trip")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


# --------------------------------------------------------------------------
# best-effort hints from testdata/<icao>_airport.json
# --------------------------------------------------------------------------
_RWY_RE = re.compile(r"^[0-9]{1,2}[LRC]?$")


def _runway_sort_key(name: str):
    m = re.match(r"^(\d+)([A-Z]*)$", name)
    return (int(m.group(1)), m.group(2)) if m else (999, name)


def _load_airport(icao: str, dirs) -> dict | None:
    icao = icao.strip().lower()
    if not re.fullmatch(r"[a-z0-9]{3,4}", icao):
        return None
    for d in dirs:
        f = Path(d) / f"{icao}_airport.json"
        if f.is_file():
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return None
            return data if isinstance(data, dict) else None
    return None


def extract_runways(data) -> list:
    """Runways are roads[] entries with type == 2 (KBUR: 8, 15, 26, 33); fall
    back to anything with a glide slope whose name looks like a designator."""
    roads = data.get("roads") if isinstance(data, dict) else None
    if not isinstance(roads, list):
        return []
    found = []
    for r in roads:
        if not isinstance(r, dict) or not isinstance(r.get("name"), str):
            continue
        name = r["name"].strip().upper()
        if not name:
            continue
        gs = r.get("glide_slope")
        is_rwy = r.get("type") == 2 or (isinstance(gs, (int, float)) and gs > 0 and _RWY_RE.match(name))
        if is_rwy and name not in found:
            found.append(name)
    return sorted(found, key=_runway_sort_key)


def extract_areas(data) -> list:
    """Terminal groups the game's GROUND owns are named Terminal<X>; derive them
    from gate road names (gate_B3 -> TerminalB)."""
    roads = data.get("roads") if isinstance(data, dict) else None
    if not isinstance(roads, list):
        return []
    found = []
    for r in roads:
        if not isinstance(r, dict) or not isinstance(r.get("name"), str):
            continue
        m = re.fullmatch(r"gate_([A-Za-z]+)\d*", r["name"].strip())
        if m:
            area = "Terminal" + m.group(1).upper()
            if area not in found:
                found.append(area)
    return sorted(found)


def runway_hints(icao: str, dirs) -> list:
    data = _load_airport(icao, dirs)
    return extract_runways(data) if data else []


def area_hints(icao: str, dirs) -> list:
    data = _load_airport(icao, dirs)
    return extract_areas(data) if data else []


# --------------------------------------------------------------------------
# HTTP server
# --------------------------------------------------------------------------
class EditorHandler(BaseHTTPRequestHandler):
    server_version = "PositionEditor/1.0"
    config_path: Path = default_config_path()
    hint_dirs: list = []

    # -- helpers --
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def log_message(self, fmt, *args):  # quieter one-line log
        sys.stderr.write(f"[editor] {fmt % args}\n")

    def _write_refused(self) -> str | None:
        """Cross-site request forgery guard for writes. Any web page open in the
        user's browser can fire a 'simple' (no pre-flight) POST at the fixed local
        port, so a save must come from this editor's own origin: refuse a foreign
        Origin, a cross-site Sec-Fetch-Site, and a Host that is not loopback (DNS
        rebinding). Requests without those headers (curl, scripts) are unaffected."""
        port = self.server.server_address[1]
        allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
        if port == 80:
            allowed |= {"http://127.0.0.1", "http://localhost"}
        origin = self.headers.get("Origin")
        if origin is not None and origin.strip().lower() not in allowed:
            return f"cross-origin write refused (Origin {origin.strip()!r}); only the editor page itself may save"
        site = self.headers.get("Sec-Fetch-Site")
        if site is not None and site.strip().lower() not in ("same-origin", "none"):
            return f"cross-site write refused (Sec-Fetch-Site {site.strip()!r})"
        host = self.headers.get("Host")
        if host is not None:
            try:
                hostname = urlparse("//" + host.strip()).hostname
            except ValueError:
                hostname = None
            if hostname not in ("127.0.0.1", "localhost", "::1"):
                return f"write refused for Host {host.strip()!r}; open the editor via http://127.0.0.1:{port}/"
        return None

    # -- routes --
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        icao = (q.get("icao") or [""])[0]
        if u.path in ("/", "/index.html"):
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif u.path == "/api/config":
            try:
                doc = load_config(self.config_path)
            except Exception as e:
                self._json(500, {"ok": False, "error": f"cannot read {self.config_path}: {e}"})
                return
            self._json(200, doc)
        elif u.path == "/api/runways":
            self._json(200, runway_hints(icao, self.hint_dirs))
        elif u.path == "/api/areas":
            self._json(200, area_hints(icao, self.hint_dirs))
        elif u.path == "/api/meta":
            self._json(200, {"file": str(self.config_path), "exists": self.config_path.exists(),
                             "hint_dirs": [str(d) for d in self.hint_dirs]})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/config":
            self._json(404, {"ok": False, "error": "not found"})
            return
        refused = self._write_refused()
        if refused:
            self._json(403, {"ok": False, "error": refused})
            return
        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype != "application/json":
            # also what forces browsers to pre-flight a cross-origin request (which we do not answer)
            self._json(415, {"ok": False, "error": f"Content-Type must be application/json (got {ctype or 'none'!r})"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        if n <= 0:
            self._json(400, {"ok": False, "error": "empty request body"})
            return
        if n > MAX_BODY:
            self._json(413, {"ok": False, "error": "request body too large"})
            return
        raw = self.rfile.read(n)
        try:
            posted = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._json(400, {"ok": False, "error": f"body is not valid JSON: {e}"})
            return
        if not isinstance(posted, dict):
            self._json(400, {"ok": False, "error": "top level must be a JSON object"})
            return
        normalize_config(posted)
        try:
            merged = merge_with_disk(self.config_path, posted)
            validate_config(merged)
            save_config_atomic(self.config_path, merged)
        except UnreadableConfigError as e:
            self._json(409, {"ok": False, "error": str(e)})
            return
        except ValueError as e:
            self._json(400, {"ok": False, "error": str(e)})
            return
        except OSError as e:
            self._json(500, {"ok": False, "error": f"write failed: {e}"})
            return
        self._json(200, {"ok": True, "path": str(self.config_path)})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Local web editor for positions.json (multi-position ATC layout).")
    ap.add_argument("--port", type=int, default=8765, help="port on 127.0.0.1 (default 8765)")
    ap.add_argument("--file", type=Path, default=None, help="path to positions.json (default: next to this script)")
    ap.add_argument("--no-browser", action="store_true", help="do not open the default browser")
    args = ap.parse_args(argv)

    path = (args.file or default_config_path()).expanduser().resolve()
    here = Path(__file__).resolve().parent
    hint_dirs = []
    for d in (here / "testdata", path.parent / "testdata"):
        if d not in hint_dirs:
            hint_dirs.append(d)

    try:
        load_config(path)
    except Exception as e:
        print(f"warning: {path}: {e}\n         the editor will show this error and refuse to save "
              "until the file is fixed (or moved away)", file=sys.stderr)

    EditorHandler.config_path = path
    EditorHandler.hint_dirs = hint_dirs
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", args.port), EditorHandler)
    except OSError as e:
        print(f"error: cannot listen on 127.0.0.1:{args.port}: {e}\n       try another port: --port 8766", file=sys.stderr)
        return 1

    url = f"http://127.0.0.1:{args.port}/"
    print(f"Position editor: {url}")
    print(f"Editing:         {path}{'' if path.exists() else '  (will be created on first save)'}")
    print("Press Ctrl+C to stop.")
    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


# --------------------------------------------------------------------------
# the editor page (vanilla HTML/CSS/JS, no external resources)
# --------------------------------------------------------------------------
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Position editor</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #f4f6f8; --card: #ffffff; --fg: #1b1f24; --muted: #5b6672; --line: #d7dde4;
    --accent: #2563eb; --accent-fg: #ffffff; --ok: #15803d; --ok-bg: #ecfdf3;
    --err: #b91c1c; --err-bg: #fef2f2; --warn: #9a5b00; --warn-bg: #fff7e6;
    --human: #6d28d9; --human-bg: #f1ebfe; --ai: #0e7490; --ai-bg: #e6f6fa;
    --radius: 8px; --hover: #eef2f7;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #10141a; --card: #191f27; --fg: #e5e9ef; --muted: #98a3b0; --line: #2a333e;
      --accent: #60a5fa; --accent-fg: #0b1220; --ok: #4ade80; --ok-bg: #0f2a1a;
      --err: #f87171; --err-bg: #2b1515; --warn: #fbbf24; --warn-bg: #2a2310;
      --human: #c4b5fd; --human-bg: #2a2144; --ai: #67e8f9; --ai-bg: #0f2a31; --hover: #222a34;
    }
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--fg);
    font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
  main { max-width: 1100px; margin: 0 auto; padding: 8px 16px 48px; }
  h1 { font-size: 18px; margin: 0; }
  h2 { font-size: 15px; margin: 0 0 10px; }
  p { margin: 0 0 10px; }
  .muted { color: var(--muted); }
  .small { font-size: 12px; }
  code, pre { font-family: ui-monospace, Consolas, "Cascadia Mono", Menlo, monospace; }
  .top { position: sticky; top: 0; z-index: 5; background: var(--card); border-bottom: 1px solid var(--line); }
  .top-inner { max-width: 1100px; margin: 0 auto; padding: 10px 16px; display: flex; flex-wrap: wrap;
    gap: 10px 16px; align-items: center; justify-content: space-between; }
  .toolbar { display: flex; gap: 8px; flex-wrap: wrap; }
  .status { max-width: 1100px; margin: 0 auto; padding: 0 16px 8px; min-height: 8px; font-weight: 600; }
  .status.ok { color: var(--ok); } .status.err { color: var(--err); }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
    padding: 14px 16px; margin: 14px 0; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 10px; }
  button, select, input[type=text] { font: inherit; color: var(--fg); background: var(--card);
    border: 1px solid var(--line); border-radius: 6px; padding: 5px 9px; }
  input[type=text] { width: 100%; }
  button { cursor: pointer; }
  button:hover { background: var(--hover); }
  button.primary { background: var(--accent); color: var(--accent-fg); border-color: var(--accent); font-weight: 600; }
  button.primary:hover { filter: brightness(1.08); }
  button.danger { color: var(--err); }
  :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
  .scroll { overflow-x: auto; }
  table.grid { border-collapse: collapse; width: 100%; }
  table.grid th, table.grid td { padding: 5px 6px; border-bottom: 1px solid var(--line); text-align: left;
    vertical-align: middle; white-space: nowrap; }
  table.grid th { font-weight: 600; font-size: 12px; color: var(--muted); }
  table.grid td.ro { color: var(--muted); font-size: 12px; white-space: normal; }
  .badge { display: inline-block; font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 10px;
    margin-left: 6px; vertical-align: middle; }
  .badge.ai { background: var(--ai-bg); color: var(--ai); }
  .badge.human { background: var(--human-bg); color: var(--human); }
  .badge.note { background: var(--warn-bg); color: var(--warn); }
  .badge.conflict { background: var(--err-bg); color: var(--err); }
  table.matrix th, table.matrix td { text-align: center; }
  table.matrix td.conflict { background: var(--err-bg); }
  table.matrix th:first-child, table.matrix td:first-child { text-align: left; font-weight: 600; }
  table.matrix tbody tr:hover { background: var(--hover); }
  table.matrix input[type=radio] { width: 18px; height: 18px; margin: 0; cursor: pointer; }
  table.matrix label { display: block; padding: 4px 0; cursor: pointer; }
  .summary { font-weight: 600; margin: 8px 0; }
  .overview { list-style: none; padding: 0; margin: 0; }
  .overview li { padding: 4px 8px; border-radius: 6px; cursor: pointer; }
  .overview li:hover { background: var(--hover); }
  .overview li[aria-current=true] { background: var(--hover); box-shadow: inset 3px 0 0 var(--accent); }
  .overview b { display: inline-block; min-width: 3.5em; }
  ul.checks { margin: 8px 0 0; padding: 8px 12px 8px 28px; border-radius: 6px; background: var(--warn-bg); color: var(--warn); }
  ul.checks li.info { color: var(--muted); }
  pre#preview { margin: 0; padding: 12px; background: var(--bg); border: 1px solid var(--line); border-radius: 6px;
    overflow: auto; max-height: 60vh; font-size: 12px; }
  #airport-select { min-width: 110px; }
  .hint { font-size: 12px; color: var(--muted); margin-top: 8px; }
  @media (max-width: 640px) { table.grid th, table.grid td { padding: 4px; } .top-inner { padding: 8px 12px; } }
</style>
</head>
<body>
<header class="top">
  <div class="top-inner">
    <div>
      <h1>Position editor</h1>
      <div class="muted small" id="file-line">Loading…</div>
    </div>
    <div class="toolbar" role="toolbar" aria-label="File actions">
      <button id="btn-save" class="primary" type="button" title="Save to positions.json (Ctrl+S)" disabled>Save</button>
      <button id="btn-reload" type="button" title="Discard unsaved edits and re-read the file">Reload</button>
      <button id="btn-download" type="button" title="Download the current document as a .json file" disabled>Download JSON</button>
    </div>
  </div>
  <div id="status" class="status" role="status" aria-live="polite"></div>
</header>

<main>
  <section class="card">
    <h2>1 · Airport</h2>
    <div class="row">
      <label for="airport-select">Airport</label>
      <select id="airport-select" aria-label="Select airport"></select>
      <button id="btn-add-airport" type="button" disabled>Add airport…</button>
      <button id="btn-remove-airport" type="button" class="danger" disabled>Remove airport</button>
    </div>
    <div id="summary" class="summary"></div>
    <ul id="overview" class="overview" aria-label="All airports in this file"></ul>
    <ul id="checks" class="checks" hidden aria-label="Checks"></ul>
    <p id="empty-note" class="muted" hidden>No airports in this file yet — use “Add airport…”.</p>
  </section>

  <div id="airport-sections">
    <section class="card">
      <h2>2 · Runways at this airport</h2>
      <p class="muted small">Comma-separated runway designators. Pre-filled from the airport data when it is available,
        merged with any runway already assigned below. This list drives the ownership matrix.</p>
      <input id="runways" type="text" placeholder="e.g. 24L, 24R, 6L, 6R" aria-label="Runways at this airport" autocomplete="off" spellcheck="false">
      <div id="runway-hint" class="hint"></div>
    </section>

    <section class="card">
      <h2>3 · Positions</h2>
      <div class="scroll">
        <table class="grid" id="positions-table">
          <thead><tr>
            <th>Name</th><th>Role</th><th>Controlled by</th><th>Frequency</th><th>Owns areas</th><th>Owns runways</th><th></th>
          </tr></thead>
          <tbody></tbody>
        </table>
      </div>
      <div class="row" style="margin-top:10px">
        <button id="btn-add-position" type="button">Add position</button>
        <span class="muted small">Runways are assigned in the matrix below; areas are a comma-separated list.</span>
      </div>
      <div id="area-hints" class="hint"></div>
    </section>

    <section class="card">
      <h2>4 · Runway ownership</h2>
      <p class="muted small">Each runway has exactly one owner. Pick the position that controls it, or leave it unassigned.</p>
      <div class="scroll" id="matrix"></div>
    </section>

    <section class="card">
      <h2>5 · Handoffs</h2>
      <p class="muted small">When the event fires, ownership moves from <em>from</em> (blank = any) to <em>to</em>
        (blank = the aircraft leaves the airport). Events: <code>landed_on:&lt;rwy&gt;</code>, <code>landed_on:*</code>,
        <code>holding_short:&lt;rwy&gt;</code>, <code>crossed:&lt;rwy&gt;</code>, <code>reached:&lt;area&gt;</code>.</p>
      <div class="scroll">
        <table class="grid" id="handoffs-table">
          <thead><tr><th>When</th><th>From</th><th>To</th><th></th></tr></thead>
          <tbody></tbody>
        </table>
      </div>
      <datalist id="when-list"></datalist>
      <div class="row" style="margin-top:10px"><button id="btn-add-handoff" type="button">Add handoff</button></div>
    </section>

    <section class="card">
      <h2>6 · Preview — exactly what Save writes</h2>
      <pre id="preview" aria-label="JSON preview"></pre>
    </section>
  </div>
</main>

<script>
(function () {
'use strict';

const ROLES = ['local', 'ground', 'ramp', 'departure', 'clearance'];
const KIND_OPTIONS = [['human', 'Human'], ['ai', 'AI']];
const state = { doc: null, icao: null, filePath: '', dirty: false, master: {}, hints: {}, token: 0 };

// ---------- tiny DOM helpers ----------
const $ = (sel, root) => (root || document).querySelector(sel);
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  if (attrs) for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'checked' || k === 'disabled' || k === 'selected' || k === 'hidden') e[k] = !!v;
    else if (k === 'value') e.value = v;
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null) continue;
    e.appendChild(typeof kid === 'string' ? document.createTextNode(kid) : kid);
  }
  return e;
}
function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); }
function uniq(a) { return a.filter((x, i) => a.indexOf(x) === i); }
function splitRunways(s) { return uniq(String(s || '').split(/[,\s]+/).map(x => x.trim().toUpperCase()).filter(Boolean)); }
function splitAreas(s) { return uniq(String(s || '').split(',').map(x => x.trim()).filter(Boolean)); }
function rwyKey(r) { const m = /^(\d+)([A-Z]*)$/.exec(r); return m ? [parseInt(m[1], 10), m[2]] : [999, r]; }
function sortRunways(list) {
  return list.slice().sort((a, b) => { const [na, sa] = rwyKey(a), [nb, sb] = rwyKey(b); return na - nb || (sa < sb ? -1 : sa > sb ? 1 : 0); });
}

// ---------- model accessors (defensive: never throw on missing fields) ----------
function airports() {
  const d = state.doc || {};
  return Object.keys(d).filter(k => !k.startsWith('_') && d[k] && typeof d[k] === 'object' && !Array.isArray(d[k]));
}
function ap() { return state.icao && state.doc && state.doc[state.icao] && typeof state.doc[state.icao] === 'object' ? state.doc[state.icao] : null; }
function listOf(o, k) { const v = o ? o[k] : null; return Array.isArray(v) ? v.map(x => String(x)) : []; }
function setList(o, k, arr) { if (!arr.length && !(k in o)) return; o[k] = arr; }
function isObj(x) { return x && typeof x === 'object' && !Array.isArray(x); }
function positions(a) { a = a || ap(); if (!a) return []; if (!Array.isArray(a.positions)) a.positions = []; return a.positions; }
function handoffs(a) { a = a || ap(); if (!a) return []; if (!Array.isArray(a.handoffs)) a.handoffs = []; return a.handoffs; }
function normalizeAirport(a) {
  if (!a) return;
  a.positions = positions(a).filter(isObj);
  a.handoffs = handoffs(a).filter(isObj);
  a.handoffs.forEach(hh => { if (!('to' in hh)) hh.to = null; });
  linkHandoffs(a);
}
// Handoffs reference positions by name in the file. While editing we also keep a hidden
// (non-enumerable, never serialised) link to the position *object*, so renaming a position
// follows through to its handoffs even when the new name transiently collides with another.
function setRef(o, k, v) { Object.defineProperty(o, k, { value: v, enumerable: false, writable: true, configurable: true }); }
function linkHandoffs(a) {
  a = a || ap(); if (!a) return;
  const ps = positions(a);
  const byName = n => { const m = ps.filter(p => String(p.name) === n); return m.length === 1 ? m[0] : null; };
  handoffs(a).forEach(hh => {
    for (const f of ['from', 'to']) {
      const refKey = '_' + f + 'Ref'; const cur = hh[refKey];
      const name = hh[f] == null ? null : String(hh[f]);
      if (name === null) { if (cur) setRef(hh, refKey, null); continue; }
      if (cur && ps.includes(cur) && String(cur.name) === name) continue;   // still consistent
      setRef(hh, refKey, byName(name));                                     // null if unknown / ambiguous
    }
  });
}
function posName(p, i) { const n = String((p && p.name) || '').trim(); return n || ('(unnamed #' + (i + 1) + ')'); }
function kindLabel(p) { return p && p.kind === 'human' ? 'Human' : 'AI'; }
function refRunways(a) { return uniq(positions(a).flatMap(p => listOf(p, 'owns_runways'))); }
function masterList() { return state.master[state.icao] || []; }
function matrixRunways() { return uniq([...masterList(), ...refRunways()]); }
function ownersOf(rwy) { return positions().map((p, i) => listOf(p, 'owns_runways').includes(rwy) ? i : -1).filter(i => i >= 0); }
function setOwner(rwy, idx) {
  positions().forEach((p, i) => {
    const cur = listOf(p, 'owns_runways');
    const has = cur.includes(rwy);
    if (i === idx) { if (!has || cur.length !== uniq(cur).length) p.owns_runways = uniq([...cur, rwy]); }
    else if (has) setList(p, 'owns_runways', cur.filter(r => r !== rwy));
  });
}
function uniqueName(base) {
  const names = positions().map(p => String(p.name || ''));
  if (!names.includes(base)) return base;
  for (let n = 2; ; n++) if (!names.includes(base + n)) return base + n;
}
// Trim the identifiers that are matched by exact string comparison (mirrors normalize_config on the
// server): position names, runway/area designators, handoff event keys and position references.
// Done at save time -- not on every keystroke, which would eat the space in "Ramp AI" as it is typed.
function normalizeDoc(d) {
  if (!isObj(d)) return d;
  for (const code of Object.keys(d)) {
    if (code.startsWith('_') || !isObj(d[code])) continue;
    const a = d[code];
    (Array.isArray(a.positions) ? a.positions : []).forEach(p => {
      if (!isObj(p)) return;
      if (typeof p.name === 'string') p.name = p.name.trim();
      for (const k of ['owns_runways', 'owns_areas']) if (Array.isArray(p[k])) p[k] = p[k].map(x => typeof x === 'string' ? x.trim() : x);
    });
    (Array.isArray(a.handoffs) ? a.handoffs : []).forEach(hh => {
      if (!isObj(hh)) return;
      for (const k of ['when', 'from', 'to']) if (typeof hh[k] === 'string') hh[k] = hh[k].trim();
    });
  }
  return d;
}
function normalizedCopy(d) { return d ? normalizeDoc(JSON.parse(JSON.stringify(d))) : {}; }

// ---------- formatting (mirrors dumps_config in the Python server) ----------
function jsonInline(v) {
  if (v === undefined) return 'null';
  if (Array.isArray(v)) return '[' + v.map(jsonInline).join(', ') + ']';
  if (v && typeof v === 'object') return '{' + Object.keys(v).map(k => JSON.stringify(k) + ': ' + jsonInline(v[k])).join(', ') + '}';
  return JSON.stringify(v);
}
function fmtDoc(d) {
  d = d || {};
  const keys = Object.keys(d); const out = ['{'];
  keys.forEach((k, i) => {
    const v = d[k]; const comma = i < keys.length - 1 ? ',' : '';
    if (isObj(v) && Array.isArray(v.positions)) {
      out.push('  ' + JSON.stringify(k) + ': {');
      const sk = Object.keys(v);
      sk.forEach((s, j) => {
        const sv = v[s]; const c2 = j < sk.length - 1 ? ',' : '';
        if ((s === 'positions' || s === 'handoffs') && Array.isArray(sv) && sv.every(isObj)) {
          if (!sv.length) out.push('    ' + JSON.stringify(s) + ': []' + c2);
          else {
            out.push('    ' + JSON.stringify(s) + ': [');
            sv.forEach((x, n) => out.push('      ' + jsonInline(x) + (n < sv.length - 1 ? ',' : '')));
            out.push('    ]' + c2);
          }
        } else {
          out.push('    ' + JSON.stringify(s) + ': ' + JSON.stringify(sv === undefined ? null : sv, null, 2).replace(/\n/g, '\n    ') + c2);
        }
      });
      out.push('  }' + comma);
    } else {
      out.push('  ' + JSON.stringify(k) + ': ' + JSON.stringify(v === undefined ? null : v, null, 2).replace(/\n/g, '\n  ') + comma);
    }
  });
  out.push('}');
  return out.join('\n') + '\n';
}

// ---------- summary + checks ----------
function summaryFor(a) {
  const parts = positions(a).map((p, i) => {
    const name = posName(p, i); const kl = kindLabel(p);
    const who = name.toLowerCase() === kl.toLowerCase() ? name : name + ' (' + kl + ')';
    const r = listOf(p, 'owns_runways'); const ar = listOf(p, 'owns_areas');
    if (r.length) return who + ' owns ' + r.join(', ');
    const role = String(p.role || '?');
    if (ar.length) return who + ' ' + role + ': ' + ar.slice(0, 3).join(', ') + (ar.length > 3 ? ' +' + (ar.length - 3) + ' more' : '');
    return who + ' ' + role;
  });
  return parts.length ? parts.join(' · ') : 'no positions';
}
function fileChecks() {
  const d = state.doc; if (!isObj(d)) return [];
  return Object.keys(d).filter(k => !k.startsWith('_') && !isObj(d[k])).map(k => ({ level: 'warn',
    text: 'Top-level key "' + k + '" is not an airport entry (its value is not an object) — Save will be refused. '
      + 'Rename it to "_' + k + '" to keep it as metadata, or remove it from the file.' }));
}
function computeChecks() {
  const w = []; const ps = positions(); const names = ps.map(p => String(p.name || '').trim());
  ps.forEach((p, i) => {
    const n = names[i]; const raw = String(p.name == null ? '' : p.name);
    if (!n) w.push({ level: 'warn', text: 'Position #' + (i + 1) + ' has no name.' });
    else if (names.indexOf(n) !== i) w.push({ level: 'warn', text: 'Duplicate position name "' + n + '" — names must be unique.' });
    else if (raw !== n) w.push({ level: 'info', text: 'Position name "' + raw + '" has leading/trailing spaces — they are removed on Save.' });
    if (!ROLES.includes(p.role)) w.push({ level: 'warn', text: posName(p, i) + ' has an unknown role "' + p.role + '".' });
    if (p.kind != null && p.kind !== 'ai' && p.kind !== 'human') w.push({ level: 'warn', text: posName(p, i) + ' has an unknown kind "' + p.kind + '".' });
  });
  const master = masterList();
  matrixRunways().forEach(r => {
    const o = ownersOf(r);
    if (o.length > 1) w.push({ level: 'warn', text: 'Runway ' + r + ' is owned by ' + o.map(i => posName(ps[i], i)).join(' and ') + ' — pick one owner in the matrix.' });
    if (!master.includes(r)) w.push({ level: 'info', text: 'Runway ' + r + ' is assigned to ' + posName(ps[o[0]], o[0]) + ' but is not in the runway list above.' });
  });
  handoffs().forEach((hh, j) => {
    const label = 'Handoff #' + (j + 1) + (hh.when ? ' (' + hh.when + ')' : '');
    if (!String(hh.when || '').trim()) w.push({ level: 'warn', text: label + ': "when" is empty.' });
    if (hh.from != null && !names.includes(String(hh.from))) w.push({ level: 'warn', text: label + ': "from" refers to unknown position "' + hh.from + '".' });
    if (hh.to != null && !names.includes(String(hh.to))) w.push({ level: 'warn', text: label + ': "to" refers to unknown position "' + hh.to + '".' });
  });
  if (ps.length && !ps.some(p => p.kind === 'human')) w.push({ level: 'info', text: 'No human position at this airport — every position is AI-controlled.' });
  return w;
}

// ---------- rendering ----------
function badge(p) { const k = kindLabel(p); return h('span', { class: 'badge ' + k.toLowerCase(), text: k }); }

function renderHeader() {
  $('#file-line').textContent = state.filePath ? 'Editing ' + state.filePath : '';
}

function renderToolbar() {
  // state.doc is null until a document has actually been loaded (and after a failed load):
  // nothing may be saved, downloaded or added to a document we do not have.
  const ok = !!state.doc;
  $('#btn-save').disabled = !ok; $('#btn-download').disabled = !ok; $('#btn-add-airport').disabled = !ok;
}

function renderAirportSelect() {
  const sel = $('#airport-select'); clear(sel);
  const list = airports();
  list.forEach(code => sel.appendChild(h('option', { value: code, text: code })));
  sel.value = state.icao || '';
  sel.disabled = !list.length;
  $('#btn-remove-airport').disabled = !state.icao;
  $('#empty-note').hidden = !!list.length || !state.doc;
  $('#airport-sections').hidden = !state.icao;

  const ov = $('#overview'); clear(ov);
  list.forEach(code => {
    const li = h('li', { role: 'button', tabindex: '0', 'aria-current': code === state.icao ? 'true' : null,
      onclick: () => selectAirport(code),
      onkeydown: e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectAirport(code); } } },
      h('b', { text: code }), ' — ', summaryFor(state.doc[code]));
    ov.appendChild(li);
  });
  const a = ap();
  $('#summary').textContent = a ? state.icao + ': ' + summaryFor(a) : '';
}

function renderChecks() {
  const ul = $('#checks'); clear(ul);
  const items = fileChecks().concat(state.icao ? computeChecks() : []);
  items.forEach(it => ul.appendChild(h('li', { class: it.level, text: it.text })));
  ul.hidden = !items.length;
}

function renderRunways() {
  const inp = $('#runways');
  if (document.activeElement !== inp) inp.value = masterList().join(', ');
  const hints = state.hints[state.icao];
  $('#runway-hint').textContent = hints && hints.runways.length
    ? 'From airport data: ' + hints.runways.join(', ')
    : 'No airport data found for ' + (state.icao || '') + ' — type the runways by hand.';
}

function renderPositions() {
  const tb = $('#positions-table tbody'); clear(tb);
  positions().forEach((p, i) => {
    const fk = f => 'pos:' + i + ':' + f;
    const nameInp = h('input', { type: 'text', value: p.name == null ? '' : String(p.name), 'data-fk': fk('name'),
      'aria-label': 'Position name', placeholder: 'Name', autocomplete: 'off', spellcheck: 'false',
      oninput: e => {
        p.name = e.target.value;
        handoffs().forEach(hh => { if (hh._fromRef === p) hh.from = p.name; if (hh._toRef === p) hh.to = p.name; });
        changed();
      } });
    const roleSel = h('select', { 'data-fk': fk('role'), 'aria-label': 'Role', onchange: e => { p.role = e.target.value; changed(); } },
      ROLES.map(r => h('option', { value: r, text: r })));
    if (!ROLES.includes(p.role)) roleSel.appendChild(h('option', { value: String(p.role), text: String(p.role) + ' (unknown)' }));
    roleSel.value = String(p.role == null ? 'local' : p.role);
    const kindSel = h('select', { 'data-fk': fk('kind'), 'aria-label': 'Controlled by', onchange: e => { p.kind = e.target.value; changed(); } },
      KIND_OPTIONS.map(([v, l]) => h('option', { value: v, text: l })));
    kindSel.value = p.kind === 'human' ? 'human' : 'ai';
    const freqInp = h('input', { type: 'text', value: p.frequency == null ? '' : String(p.frequency), 'data-fk': fk('freq'),
      'aria-label': 'Frequency', placeholder: '118.7', autocomplete: 'off', style: 'width:6.5em',
      oninput: e => { const v = e.target.value; if (v === '' && !('frequency' in p)) return; p.frequency = v; changed(); } });
    const areasInp = h('input', { type: 'text', value: listOf(p, 'owns_areas').join(', '), 'data-fk': fk('areas'),
      'aria-label': 'Owned areas, comma-separated', placeholder: 'ramp, TerminalA', autocomplete: 'off', spellcheck: 'false', style: 'min-width:14em',
      oninput: e => { setList(p, 'owns_areas', splitAreas(e.target.value)); changed(); } });
    const rw = listOf(p, 'owns_runways');
    const removeBtn = h('button', { type: 'button', class: 'danger', 'data-fk': fk('rm'), 'aria-label': 'Remove ' + posName(p, i),
      onclick: () => {
        const owned = listOf(p, 'owns_runways');
        const msg = 'Remove position "' + posName(p, i) + '"?' + (owned.length ? ' Its runways (' + owned.join(', ') + ') become unassigned.' : '');
        if (!confirm(msg)) return;
        positions().splice(i, 1); changed();
      } }, 'Remove');
    tb.appendChild(h('tr', null,
      h('td', null, nameInp), h('td', null, roleSel), h('td', null, kindSel), h('td', null, freqInp), h('td', null, areasInp),
      h('td', { class: 'ro', title: 'Assigned in the runway ownership matrix' }, rw.length ? rw.join(', ') : '—'),
      h('td', null, removeBtn)));
  });
  const hints = state.hints[state.icao];
  $('#area-hints').textContent = hints && hints.areas.length ? 'Areas seen in airport data: ' + hints.areas.join(', ') : '';
}

function renderMatrix() {
  const box = $('#matrix'); clear(box);
  const rows = matrixRunways(); const ps = positions(); const master = masterList();
  if (!rows.length) { box.appendChild(h('p', { class: 'muted', text: 'No runways yet — add them in the runway list above.' })); return; }
  if (!ps.length) { box.appendChild(h('p', { class: 'muted', text: 'Add a position first, then assign runways here.' })); return; }
  const head = h('tr', null, h('th', { text: 'Runway' }),
    ps.map((p, i) => h('th', { scope: 'col' }, posName(p, i), badge(p))),
    h('th', { scope: 'col', text: '(unassigned)' }));
  const body = ps.length ? rows.map(r => {
    const owners = ownersOf(r);
    // A runway with several owners (hand-edited file) gets NO pre-checked radio: a checked radio
    // fires no change event, so pre-checking owners[0] would make "keep A" impossible to click.
    const current = owners.length === 1 ? owners[0] : (owners.length ? null : -1);
    const cell = (idx, label) => {
      const id = 'rwy-' + r + '-' + idx;
      return h('td', { class: owners.length > 1 && owners.includes(idx) ? 'conflict' : null }, h('label', { for: id },
        h('input', { type: 'radio', id, name: 'rwy-' + r, value: String(idx), checked: current === idx, 'data-fk': 'rwy:' + r + ':' + idx,
          'aria-label': r + ': ' + label, onchange: () => { setOwner(r, idx); changed(); } })));
    };
    return h('tr', null,
      h('td', null, r, master.includes(r) ? null : h('span', { class: 'badge note', text: 'not in list', title: 'Assigned to a position but missing from the runway list' }),
        owners.length > 1 ? h('span', { class: 'badge conflict', text: owners.length + ' owners', title: 'Owned by more than one position — pick the one that keeps it' }) : null),
      ps.map((p, i) => cell(i, 'owned by ' + posName(p, i))),
      cell(-1, 'unassigned'));
  }) : [];
  box.appendChild(h('table', { class: 'grid matrix' }, h('thead', null, head), h('tbody', null, body)));
}

function renderHandoffs() {
  const tb = $('#handoffs-table tbody'); clear(tb);
  const names = positions().map(p => String(p.name == null ? '' : p.name));
  const mkSel = (hh, field, blankLabel, j) => {
    const cur = hh[field] == null ? '' : String(hh[field]);
    const sel = h('select', { 'data-fk': 'ho:' + j + ':' + field, 'aria-label': field,
      onchange: e => { hh[field] = e.target.value === '' ? null : e.target.value; changed(); } },
      h('option', { value: '', text: blankLabel }),
      names.filter(Boolean).map(n => h('option', { value: n, text: n })));
    if (cur !== '' && !names.includes(cur)) sel.appendChild(h('option', { value: cur, text: cur + ' (unknown)' }));
    sel.value = cur;
    return sel;
  };
  handoffs().forEach((hh, j) => {
    const whenInp = h('input', { type: 'text', list: 'when-list', value: hh.when == null ? '' : String(hh.when), 'data-fk': 'ho:' + j + ':when',
      'aria-label': 'When (event)', placeholder: 'landed_on:24R', autocomplete: 'off', spellcheck: 'false', style: 'min-width:12em',
      oninput: e => { hh.when = e.target.value; changed(); } });
    const rm = h('button', { type: 'button', class: 'danger', 'data-fk': 'ho:' + j + ':rm', 'aria-label': 'Remove handoff ' + (j + 1),
      onclick: () => { handoffs().splice(j, 1); changed(); } }, 'Remove');
    tb.appendChild(h('tr', null, h('td', null, whenInp), h('td', null, mkSel(hh, 'from', '(any)', j)),
      h('td', null, mkSel(hh, 'to', '(leaves airport)', j)), h('td', null, rm)));
  });
  const dl = $('#when-list'); clear(dl);
  const rws = matrixRunways();
  const opts = ['landed_on:*', ...rws.map(r => 'landed_on:' + r), 'reached:ramp',
    ...rws.map(r => 'holding_short:' + r), ...rws.map(r => 'crossed:' + r)];
  uniq(positions().flatMap(p => listOf(p, 'owns_areas'))).forEach(a => { if (a !== 'ramp') opts.push('reached:' + a); });
  uniq(opts).forEach(o => dl.appendChild(h('option', { value: o })));
}

function renderPreview() { $('#preview').textContent = fmtDoc(normalizedCopy(state.doc)); }   // what Save will write, trimmed

function renderAll() {
  const active = document.activeElement;
  const key = active && active.dataset ? active.dataset.fk : null;
  const caret = active && typeof active.selectionStart === 'number' ? active.selectionStart : null;
  renderHeader(); renderToolbar(); renderAirportSelect(); renderChecks();
  if (state.icao) { renderRunways(); renderPositions(); renderMatrix(); renderHandoffs(); }
  renderPreview();
  if (key) {
    const e = document.querySelector('[data-fk="' + CSS.escape(key) + '"]');
    if (e && e !== document.activeElement) {
      e.focus();
      try { if (caret != null && e.setSelectionRange) e.setSelectionRange(caret, caret); } catch (_) { /* not a text input */ }
    }
  }
}

function changed() { state.dirty = true; linkHandoffs(ap()); setStatus('Unsaved changes', ''); renderAll(); }
function setStatus(msg, kind) { const s = $('#status'); s.textContent = msg; s.className = 'status' + (kind ? ' ' + kind : ''); }

// ---------- server I/O ----------
async function fetchJSON(url, opts) {
  const r = await fetch(url, opts);
  let body = null; try { body = await r.json(); } catch (_) { body = null; }
  if (!r.ok) throw new Error((body && body.error) || ('HTTP ' + r.status));
  return body;
}
async function getHints(code) {
  if (state.hints[code]) return state.hints[code];
  let runways = [], areas = [];
  try { runways = await fetchJSON('/api/runways?icao=' + encodeURIComponent(code)); } catch (_) { runways = []; }
  try { areas = await fetchJSON('/api/areas?icao=' + encodeURIComponent(code)); } catch (_) { areas = []; }
  const r = { runways: Array.isArray(runways) ? runways.map(String) : [], areas: Array.isArray(areas) ? areas.map(String) : [] };
  state.hints[code] = r;
  return r;
}
async function selectAirport(code) {
  const token = ++state.token;
  if (code && !(code in state.master)) {
    const hints = await getHints(code);
    if (token !== state.token) return;
    state.master[code] = sortRunways(uniq([...hints.runways, ...refRunways(state.doc[code])]));
  }
  state.icao = code || null;
  normalizeAirport(ap());
  renderAll();
}
async function load() {
  setStatus('Loading…', '');
  try {
    const cfg = await fetchJSON('/api/config');
    let meta = {}; try { meta = await fetchJSON('/api/meta'); } catch (_) { meta = {}; }
    state.doc = isObj(cfg) ? cfg : {};
    state.filePath = meta.file || '';
    state.master = {}; state.dirty = false;
    const list = airports();
    await selectAirport(list.includes(state.icao) ? state.icao : (list[0] || null));
    setStatus(meta.exists === false ? 'File does not exist yet — it will be created on Save.' : '', '');
  } catch (e) {
    // No document: leave state.doc null so Save / Download / Add airport stay disabled (renderToolbar)
    // and Ctrl+S cannot write an empty document over a file that merely failed to parse.
    state.doc = null; state.icao = null; state.dirty = false;
    renderAll();
    setStatus('Load failed: ' + e.message + ' — saving is disabled until the file can be read; fix it on disk (or move it away), then click Reload.', 'err');
  }
}
async function save() {
  if (!state.doc) { setStatus('Nothing to save — the file could not be loaded. Fix it on disk, then click Reload.', 'err'); return; }
  normalizeDoc(state.doc); linkHandoffs(ap()); renderAll();   // trim names etc. in place so the page shows what was written
  setStatus('Saving…', '');
  try {
    const r = await fetch('/api/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(state.doc) });
    let j = {}; try { j = await r.json(); } catch (_) { j = {}; }
    if (r.ok && j.ok) { state.dirty = false; setStatus('Saved to ' + (j.path || state.filePath), 'ok'); }
    else setStatus('Not saved: ' + (j.error || ('HTTP ' + r.status)), 'err');
  } catch (e) { setStatus('Not saved: ' + e.message, 'err'); }
}
function download() {
  if (!state.doc) return;
  const blob = new Blob([fmtDoc(normalizedCopy(state.doc))], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'positions.json';
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

// ---------- actions ----------
async function addAirport() {
  if (!state.doc) return;
  let code = prompt('ICAO code for the new airport (3-4 letters/digits, e.g. KBUR):', '');
  if (code == null) return;
  code = code.trim().toUpperCase();
  if (!/^[A-Z0-9]{3,4}$/.test(code)) { alert('The ICAO code must be 3-4 letters or digits, e.g. KBUR.'); return; }
  if (Object.prototype.hasOwnProperty.call(state.doc, code)) {
    if (isObj(state.doc[code])) { await selectAirport(code); setStatus(code + ' already exists — selected it.', ''); }
    else alert('"' + code + '" already exists in the file but is not an airport entry.');
    return;
  }
  const hints = await getHints(code);
  state.doc[code] = {
    positions: [
      { name: 'Local', role: 'local', kind: 'ai', frequency: '', owns_runways: hints.runways.slice() },
      { name: 'Ground', role: 'ground', kind: 'ai', frequency: '', owns_areas: hints.areas.slice() }
    ],
    handoffs: [
      { when: 'landed_on:*', from: 'Local', to: 'Ground' },
      { when: 'reached:ramp', from: 'Ground', to: null }
    ]
  };
  state.dirty = true;
  await selectAirport(code);
  setStatus('Added ' + code + ' (unsaved)', '');
}
function removeAirport() {
  const code = state.icao; if (!code) return;
  if (!confirm('Remove airport ' + code + ' and all of its positions and handoffs from the file?')) return;
  delete state.doc[code]; delete state.master[code];
  state.dirty = true;
  const list = airports();
  selectAirport(list[0] || null).then(() => setStatus('Removed ' + code + ' (unsaved)', ''));
}
function addPosition() {
  positions().push({ name: uniqueName('Position'), role: 'local', kind: 'ai', frequency: '', owns_runways: [], owns_areas: [] });
  changed();
  const inp = document.querySelector('[data-fk="pos:' + (positions().length - 1) + ':name"]');
  if (inp) { inp.focus(); inp.select(); }
}
function addHandoff() {
  handoffs().push({ when: '', from: null, to: null });
  changed();
  const inp = document.querySelector('[data-fk="ho:' + (handoffs().length - 1) + ':when"]');
  if (inp) inp.focus();
}

// ---------- wiring ----------
$('#btn-save').addEventListener('click', save);
$('#btn-reload').addEventListener('click', () => { if (!state.dirty || confirm('Discard unsaved changes and reload from disk?')) load(); });
$('#btn-download').addEventListener('click', download);
$('#btn-add-airport').addEventListener('click', addAirport);
$('#btn-remove-airport').addEventListener('click', removeAirport);
$('#btn-add-position').addEventListener('click', addPosition);
$('#btn-add-handoff').addEventListener('click', addHandoff);
$('#airport-select').addEventListener('change', e => selectAirport(e.target.value));
$('#runways').addEventListener('change', e => {
  state.master[state.icao] = splitRunways(e.target.value);
  renderAll();
});
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && (e.key === 's' || e.key === 'S')) { e.preventDefault(); save(); }
});
window.addEventListener('beforeunload', e => { if (state.dirty) { e.preventDefault(); e.returnValue = ''; } });

load();
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    sys.exit(main())
