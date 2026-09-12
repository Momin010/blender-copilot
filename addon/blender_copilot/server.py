"""Newline-delimited JSON-RPC over TCP.

Runs entirely on worker threads. Never touches bpy -- every request is handed to
executor.submit(), which marshals it onto the main thread.
"""

import json
import socket
import threading

from . import executor, handlers

HOST = "127.0.0.1"
PORT = 9876

_server = None


class Server:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self._sock = None
        self._thread = None
        self._stop = threading.Event()

    def start(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self.host, self.port))
        self._sock.listen(8)
        self._sock.settimeout(0.5)
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        print(f"[blender-copilot] listening on {self.host}:{self.port}")

    def stop(self):
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        print("[blender-copilot] stopped")

    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        # Length-agnostic: requests are newline-delimited JSON, so a large
        # payload (a long script) simply spans multiple reads.
        buf = b""
        with conn:
            conn.settimeout(None)
            while not self._stop.is_set():
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    break
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    response = self._handle(line)
                    try:
                        conn.sendall(json.dumps(response).encode() + b"\n")
                    except OSError:
                        return

    def _handle(self, line):
        try:
            req = json.loads(line)
        except json.JSONDecodeError as exc:
            return {"id": None, "error": {"type": "JSONDecodeError", "message": str(exc)}}

        rid = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        fn = handlers.METHODS.get(method)
        if fn is None:
            return {"id": rid, "error": {"type": "MethodNotFound", "message": f"unknown method {method!r}"}}

        timeout = float(params.pop("_timeout", 120.0))
        result, error = executor.submit(lambda: fn(params), timeout=timeout)
        if error is not None:
            return {"id": rid, "error": error}
        return {"id": rid, "result": result}


def start():
    global _server
    if _server is not None:
        return
    executor.start()
    _server = Server()
    _server.start()


def stop():
    global _server
    if _server is not None:
        _server.stop()
        _server = None
    executor.stop()
