"""Live RWSL feed server — serves rwsl.compute(world) as JSON over localhost so
the airport-builder planner's "Live RWSL" mode can poll it and paint each stop
bar red/green. Read-only; localhost only.

Contract: GET /rwsl -> [{e, n, state, reason}, ...]  (docs/RWSL-INTERFACE.md)

Usage:
    from rwsl_feed import serve_rwsl
    serve_rwsl(lambda: rwsl.feed(world), port=8770)   # runs in a daemon thread
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable


def serve_rwsl(feed_fn: Callable[[], list], port: int = 8770,
               host: str = "127.0.0.1", background: bool = True) -> HTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.rstrip("/") not in ("", "/rwsl"):
                self.send_response(404); self.end_headers(); return
            body = json.dumps(feed_fn()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")  # local planner
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # quiet
            pass

    httpd = HTTPServer((host, port), Handler)
    if background:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd
