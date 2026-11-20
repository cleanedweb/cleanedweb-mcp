"""A stand-in for the hosted server: plain JSON responses, no sessions, no SSE."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOOLS = [
    {
        "name": "find_api",
        "title": "Find a catalog API",
        "description": "Search the catalog.",
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
        "inputSchema": {"type": "object", "properties": {"site": {"type": "string"}}, "additionalProperties": False},
        "outputSchema": {"type": "object", "properties": {"count": {"type": "integer"}}},
        "_meta": {"required_scopes": ["read", "run"]},
    },
    {
        "name": "run_api",
        "description": "Run an API.",
        "inputSchema": {"type": "object", "properties": {"api_id": {"type": "string"}}, "required": ["api_id"]},
    },
]


class FakeUpstream:
    def __init__(self) -> None:
        self.seen: list[dict] = []
        self.fail_calls_with: int | None = None
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # silence
                pass

            def do_GET(self):
                self.send_response(405)
                self.end_headers()

            def do_DELETE(self):
                self.send_response(405)
                self.end_headers()

            def _json(self, status: int, payload: dict) -> None:
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                msg = json.loads(self.rfile.read(int(self.headers["content-length"])))
                fake.seen.append(
                    {
                        "method": msg["method"],
                        "params": msg.get("params"),
                        "authorization": self.headers.get("authorization"),
                        "protocol_version": self.headers.get("mcp-protocol-version"),
                    }
                )
                if "id" not in msg:
                    self.send_response(202)
                    self.send_header("content-length", "0")
                    self.end_headers()
                    return

                def reply(result):
                    self._json(200, {"jsonrpc": "2.0", "id": msg["id"], "result": result})

                def error(code, message):
                    self._json(200, {"jsonrpc": "2.0", "id": msg["id"], "error": {"code": code, "message": message}})

                method = msg["method"]
                if method == "initialize":
                    reply(
                        {
                            "protocolVersion": "2025-06-18",
                            "capabilities": {"tools": {"listChanged": False}},
                            "serverInfo": {"name": "fake-cleanedweb", "version": "1"},
                        }
                    )
                elif method == "tools/list":
                    reply({"tools": TOOLS})
                elif method == "tools/call":
                    if fake.fail_calls_with:
                        self._json(fake.fail_calls_with, {"error": "unauthorized"})
                    elif msg["params"]["name"] == "nope":
                        error(-32602, "Unknown tool: nope")
                    else:
                        payload = {"count": 1, "echo": msg["params"].get("arguments")}
                        reply({"content": [{"type": "text", "text": json.dumps(payload)}], "structuredContent": payload})
                else:
                    error(-32601, "Method not found")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._server.server_address[1]}/mcp"
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
