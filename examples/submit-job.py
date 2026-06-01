"""Tiny fake-backend that hands the worker one job and prints the callbacks.

Run this in one terminal, then ``python examples/run-worker.py`` in another.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

JOB = {
    "id": "demo-1",
    "kind": "image",
    "lane": "image",
    "model": "sdxl-base",
    "prompt": "a fox in a snowy forest, cinematic",
    "payload": {
        "workflow": {"_demo": "replace with a real Comfy workflow dict"},
        "randomize_seeds": True,
    },
}

_state = {"served": False}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _json(self, code: int, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/api/jobs/next"):
            if _state["served"]:
                self.send_response(204)
                self.end_headers()
                return
            _state["served"] = True
            return self._json(200, JOB)
        self.send_response(404)
        self.end_headers()

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            body = {"_raw": raw.decode("utf-8", errors="replace")}
        if "/callback" in self.path:
            print(f"[callback] {json.dumps(body)}")
        elif "/ack" in self.path:
            print(f"[ack] {self.path} status={body.get('status')}")
        self._json(200, {"ok": True})


def main() -> None:
    port = int(os.environ.get("PORT", "4001"))
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"listening on http://127.0.0.1:{port}")
    print("now launch the worker in another shell:")
    print("  BACKEND_URL=http://127.0.0.1:4001/api \\")
    print("  CALLBACK_URL=http://127.0.0.1:4001/api/jobs/callback \\")
    print("  python examples/run-worker.py")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        while True:
            input()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
