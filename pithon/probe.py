"""Non-destructive capability probe for constrained Python environments."""

from __future__ import annotations

import json
import platform
import shutil
import socket
import subprocess
import sys
from typing import Any


def probe() -> dict[str, Any]:
    result: dict[str, Any] = {
        "python": sys.version,
        "platform": platform.platform(),
        "commands": {
            name: shutil.which(name)
            for name in ("ssh", "scp", "sftp", "ssh-keygen", "curl", "lg2", "git")
        },
    }
    listener: socket.socket | None = None
    try:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        result["python_listen_socket"] = {"ok": True, "address": listener.getsockname()}
    except OSError as error:
        result["python_listen_socket"] = {"ok": False, "error": repr(error)}
    finally:
        if listener is not None:
            listener.close()

    try:
        completed = subprocess.run(
            ["pwd"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        result["python_subprocess"] = {
            "ok": completed.returncode == 0,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except (OSError, subprocess.SubprocessError) as error:
        result["python_subprocess"] = {"ok": False, "error": repr(error)}

    ssh = result["commands"]["ssh"]
    if ssh:
        result["ssh_version"] = _run_bounded([ssh, "-V"])
        result["ssh_options"] = _run_bounded([ssh, "-?"])
        result["ssh_reverse_option_parse"] = _run_bounded([
            ssh,
            "-G",
            "-R",
            "127.0.0.1:49321:127.0.0.1:49320",
            "example.invalid",
        ])
    return result


def _run_bounded(command: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout[:8192],
            "stderr": completed.stderr[:8192],
        }
    except (OSError, subprocess.SubprocessError) as error:
        return {"error": repr(error)}


def main() -> int:
    print(json.dumps(probe(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
