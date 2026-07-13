"""One-shot loopback service for proving an a-Shell reverse tunnel.

This is diagnostic code, not a remote-control protocol.
"""

from __future__ import annotations

import argparse
import socket
import subprocess
import time
from pathlib import Path
from typing import Callable, Sequence

HOST = "127.0.0.1"
PORT = 49320
REMOTE_PORT = 49321
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


def build_reverse_command(
    ssh: str,
    identity: Path,
    destination: str,
    remote_port: int = REMOTE_PORT,
    local_port: int = PORT,
) -> list[str]:
    return [
        ssh,
        "-4",
        "-N",
        "-T",
        "-o",
        "BatchMode=yes",
        "-o",
        "PasswordAuthentication=no",
        "-o",
        "KbdInteractiveAuthentication=no",
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        "-i",
        str(identity),
        "-R",
        f"127.0.0.1:{remote_port}:127.0.0.1:{local_port}",
        destination,
    ]


def run_reverse_probe(
    destination: str,
    identity: Path,
    *,
    ssh: str = "ssh",
    timeout: float = 120.0,
) -> None:
    identity = identity.expanduser().resolve(strict=True)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((HOST, PORT))
        listener.listen(1)
        listener.settimeout(1.0)
        command = build_reverse_command(ssh, identity, destination)
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL)
        try:
            print(
                f"reverse tunnel requested: Mac {HOST}:{REMOTE_PORT} -> phone {HOST}:{PORT}",
                flush=True,
            )
            print("waiting for the Mac-side probe; keep a-Shell foregrounded", flush=True)
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                return_code = process.poll()
                if return_code is not None:
                    raise RuntimeError(f"ssh exited before the probe with status {return_code}")
                try:
                    connection, address = listener.accept()
                except socket.timeout:
                    continue
                with connection:
                    connection.sendall(RESPONSE)
                print(f"served Mac probe through tunnel from {address[0]}:{address[1]}", flush=True)
                return
            raise TimeoutError(f"no Mac connection arrived within {timeout:g} seconds")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reverse-to", help="SSH destination, for example cjv@100.75.134.73")
    parser.add_argument("--identity", type=Path, help="private key used for the reverse SSH connection")
    parser.add_argument("--timeout", type=float, default=120.0)
    arguments = parser.parse_args(argv)
    if arguments.reverse_to:
        if arguments.identity is None:
            parser.error("--identity is required with --reverse-to")
        run_reverse_probe(arguments.reverse_to, arguments.identity, timeout=arguments.timeout)
    else:
        serve_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
