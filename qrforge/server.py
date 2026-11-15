"""Local HTTP server for the QRForge web workbench (stdlib only)."""

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import qrforge as core
from . import tables
from .encode import CapacityError

WEB_DIR = Path(__file__).parent / "web"
DEFAULT_PORT = 8860


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(),
                   "application/json; charset=utf-8")

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/index"):
            body = (WEB_DIR / "index.html").read_bytes()
            self._send(200, body, "text/html; charset=utf-8")
        elif self.path == "/app.js":
            self._send(200, (WEB_DIR / "app.js").read_bytes(),
                       "text/javascript; charset=utf-8")
        elif self.path == "/style.css":
            self._send(200, (WEB_DIR / "style.css").read_bytes(),
                       "text/css; charset=utf-8")
        elif self.path == "/api/info":
            self._json({
                "levels": list(tables.EC_LEVELS),
                "max_version": tables.MAX_VERSION,
                "blocks": {f"{v}-{lv}": row
                           for (v, lv), row in tables.BLOCKS.items()},
            })
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        try:
            if self.path == "/api/encode":
                result = core.encode(payload.get("text", ""),
                                     level=payload.get("level", "M"))
                self._json(core.to_json(result))
            elif self.path == "/api/decode":
                rows = payload["rows"]
                m = [[ch == "1" for ch in row] for row in rows]
                self._json(core.decode(m))
            elif self.path == "/api/damage":
                result = core.encode(payload.get("text", ""),
                                     level=payload.get("level", "M"))
                damaged, flips = core.damage(result["matrix"],
                                             int(payload.get("cells", 16)),
                                             seed=int(payload.get("seed", 0)))
                try:
                    decoded = core.decode(damaged)
                except core.QRForgeError as exc:
                    decoded = {"ok": False, "text": "", "error": str(exc),
                               "corrected_bytes": 0}
                self._json({
                    "rows": ["".join("1" if v else "0" for v in row)
                             for row in damaged],
                    "flips": [[r, c] for r, c in flips],
                    "decoded": decoded,
                })
            elif self.path == "/api/masks":
                self._json(core.mask_eval(payload.get("text", ""),
                                          payload.get("level", "M")))
            elif self.path == "/api/rs":
                text = payload.get("text", "")
                level = payload.get("level", "M")
                self._json(core.rs_pipeline(text, level))
            elif self.path == "/api/bench":
                self._json(core.bench())
            else:
                self._send(404, b"not found", "text/plain")
        except core.QRForgeError as exc:
            self._json({"error": str(exc)}, 400)
        except CapacityError as exc:
            self._json({"error": str(exc)}, 400)


def serve(host="127.0.0.1", port=DEFAULT_PORT, open_browser=True):
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"qrforge workbench on {url} (Ctrl+C to stop)")
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    serve()
