"""Thin client for the in-Blender bridge. Used by the MCP server and by tests."""

import json
import socket


class BridgeError(RuntimeError):
    pass


class Bridge:
    def __init__(self, host="127.0.0.1", port=9876, timeout=180.0):
        self.host, self.port, self.timeout = host, port, timeout
        self._sock = None
        self._buf = b""
        self._id = 0

    def connect(self):
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        return self

    def close(self):
        if self._sock:
            self._sock.close()
            self._sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()
        return False

    def call(self, method, **params):
        if self._sock is None:
            self.connect()
        self._id += 1
        payload = json.dumps({"id": self._id, "method": method, "params": params})
        self._sock.sendall(payload.encode() + b"\n")

        while b"\n" not in self._buf:
            chunk = self._sock.recv(1 << 20)
            if not chunk:
                raise BridgeError("connection closed by Blender")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)

        resp = json.loads(line)
        if resp.get("error"):
            e = resp["error"]
            raise BridgeError(f"{e.get('type')}: {e.get('message')}")
        return resp.get("result")
