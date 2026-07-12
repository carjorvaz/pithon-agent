"""Opt-in, mode-restricted JSONL conversation storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class SessionError(ValueError):
    """A session file is malformed or unsafe."""


class SessionLog:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve(strict=False)
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            os.chmod(self.path.parent, 0o700)
        except OSError:
            pass

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        messages: list[dict[str, Any]] = []
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                for number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    event = json.loads(line)
                    if event.get("type") != "message" or not isinstance(event.get("message"), dict):
                        raise SessionError(f"invalid event on line {number}")
                    messages.append(event["message"])
        except (OSError, json.JSONDecodeError) as error:
            raise SessionError(f"cannot load session: {error}") from error
        return messages

    def append(self, message: dict[str, Any]) -> None:
        event = json.dumps(
            {"type": "message", "message": message},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
                handle.write(event)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
