#!/usr/bin/env python3
"""Test server: serves /hls/* from a live HLS dir and the web page; one shared bottleneck link whose
rate (kbit/s) is set with GET /__rate?kbps=N  (stand-in for the tc tbf on the Pi)."""
import os, sys, time, threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
LIVE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/live"; WEB = sys.argv[2]; PORT = int(sys.argv[3]) if len(sys.argv) > 3 else 8099
state = {"kbps": 100000.0, "free": 0.0}; lock = threading.Lock()
TYPES = {".m3u8": "application/vnd.apple.mpegurl", ".m4s": "video/iso.segment", ".mp4": "video/mp4", ".html": "text/html", ".js": "application/javascript"}

class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass
    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/__rate":
            state["kbps"] = float(parse_qs(u.query)["kbps"][0]); return self._send(b"ok", "text/plain", throttle=False)
        if u.path.startswith("/hls/"): f = os.path.join(LIVE, u.path[5:])
        else: f = os.path.join(WEB, u.path.lstrip("/") or "index.html")
        if not os.path.isfile(f): self.send_response(404); self.send_header("Content-Length", "0"); self.end_headers(); return
        self._send(open(f, "rb").read(), TYPES.get(os.path.splitext(f)[1], "application/octet-stream"), throttle=u.path.startswith("/hls/"))
    def _send(self, body, ctype, throttle=True):
        self.send_response(200); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache"); self.send_header("Access-Control-Allow-Origin", "*"); self.end_headers()
        i = 0
        while i < len(body):
            ch = body[i:i + 4096]; i += len(ch)
            if throttle:
                with lock:
                    now = time.time(); start = max(now, state["free"]); state["free"] = start + len(ch) * 8 / (state["kbps"] * 1000)
                    wait = state["free"] - now
                if wait > 0: time.sleep(wait)
            try: self.wfile.write(ch)
            except Exception: return

ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
