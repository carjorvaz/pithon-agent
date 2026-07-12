"""One-shot loopback service for proving an a-Shell reverse tunnel.

This is diagnostic code, not a remote-control protocol.
"""

from __future__ import annotations

import socket
from typing import Callable

HOST = "127.0.0.1"
PORT = 49320
RESPONSE = b"PITHON_PHONE_OK\n"


def serve_once(
    host: str = HOST,
    port: int = PORT,
    on_ready: Callable[[], None] | None = None,
) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(1)
        if on_ready is not None:
            on_ready()
        print(f"listening on {host}:{port}; waiting for one tunnel connection", flush=True)
        connection, address = listener.accept()
        with connection:
            connection.sendall(RESPONSE)
        print(f"served one connection from {address[0]}:{address[1]}", flush=True)


def main() -> int:
    serve_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
