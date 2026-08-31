"""Situational-display feed: serve the whole live picture as JSON over localhost,
so an external ground/air display (or the planner) can render every aircraft.

Companion to rwsl_feed — same localhost pattern, but the full world instead of
just the lights. GET /world -> {airport, planes:[...]}.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


def world_snapshot(world) -> dict:
    planes = []
    for cs, p in world.state.planes.items():
        planes.append({
            "callsign": cs,
            "e": (p.pos or {}).get("x"), "n": (p.pos or {}).get("z"),
            "lat": p.latlon[0] if p.latlon else None,
            "lon": p.latlon[1] if p.latlon else None,
            "heading": p.heading, "speed": p.speed, "alt": p.alt_ft,
            "phase": p.phase.name, "runway": p.runway,
            "target_runway": p.target_runway,
        })
    return {"center": world.center, "planes": planes}


def serve_world(world, port: int = 8771, host: str = "127.0.0.1",
                background: bool = True) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            # /traffic is Contract D (planner-facing name); /world is the alias
            if self.path.rstrip("/") not in ("", "/world", "/traffic"):
                self.send_response(404); self.end_headers(); return
            body = json.dumps(world_snapshot(world)).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    httpd = HTTPServer((host, port), Handler)
    if background:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
