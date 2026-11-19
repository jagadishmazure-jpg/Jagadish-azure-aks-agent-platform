"""Fixed-response stand-in for an open-weight model server.

The process reads a bounded request body and returns the same JSON every time.
It does not load weights, call the network, or copy the prompt into the response.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_BODY = 64 * 1024


def stub_body() -> bytes:
    payload = {
        "id": "stub",
        "object": "chat.completion",
        "model": os.environ.get("MODEL_ID", "northfield-open-weight-stub"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "stub"},
                "finish_reason": "stop",
            }
        ],
    }
    return json.dumps(payload).encode()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] != "/healthz":
            self._send(404, b"not found")
            return
        self._send(200, b"ok")

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/v1/chat/completions":
            self._send(404, b"not found")
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length < 0 or length > MAX_BODY:
            self._send(413, b"too large")
            return
        self.rfile.read(length)
        self._send(200, stub_body(), "application/json")

    def log_message(self, fmt: str, *args) -> None:
        return

    def _send(self, code: int, body: bytes, content_type: str = "text/plain") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    port = int(os.environ.get("PORT", "8080"))
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
