from __future__ import annotations

import socket
import threading
import unittest

from pithon import tunnel_probe


class TunnelProbeTests(unittest.TestCase):
    def test_serves_exactly_one_bounded_response(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]

        ready = threading.Event()
        thread = threading.Thread(
            target=tunnel_probe.serve_once,
            kwargs={"port": port, "on_ready": ready.set},
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(timeout=2))
        with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
            self.assertEqual(client.recv(1024), b"PITHON_PHONE_OK\n")
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())


if __name__ == "__main__":
    unittest.main()
