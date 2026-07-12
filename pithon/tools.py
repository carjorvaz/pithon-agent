"""Confirmed, workspace-confined filesystem tools."""

from __future__ import annotations

import difflib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .policy import PolicyError, WorkspacePolicy
from .redaction import redact_text

_MAX_READ_BYTES = 65_536
_MAX_TOOL_OUTPUT = 65_536
_MAX_LIST_ENTRIES = 250
_MAX_SCAN_FILES = 500
_MAX_SEARCH_MATCHES = 100

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List one workspace directory. Paths are relative to the workspace root.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "default": "."}},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a bounded inclusive line range from a UTF-8 workspace file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "start_line": {"type": "integer", "minimum": 1, "default": 1},
                    "end_line": {"type": "integer", "minimum": 1, "default": 200},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Search UTF-8 workspace files for a literal string, returning bounded line matches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Replace exactly one occurrence in a UTF-8 file after showing a diff and receiving approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_text": {"type": "string"},
                    "new_text": {"type": "string"},
                },
                "required": ["path", "old_text", "new_text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or replace a UTF-8 file after showing a diff and receiving approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    },
]


class ToolRegistry:
    def __init__(self, policy: WorkspacePolicy) -> None:
        self.policy = policy

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        try:
            handlers = {
                "list_files": self._list_files,
                "read_file": self._read_file,
                "search_text": self._search_text,
                "edit_file": self._edit_file,
                "write_file": self._write_file,
            }
            handler = handlers.get(name)
            if handler is None:
                return self._result(False, error=f"unknown tool: {name}")
            result = handler(arguments)
            return self._result(True, result=result)
        except (PolicyError, OSError, UnicodeError, ValueError, TypeError) as error:
            return self._result(False, error=str(error))

    def _list_files(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self.policy.resolve(arguments.get("path", "."))
        if not path.is_dir():
            raise ValueError("path is not a directory")
        entries: list[dict[str, Any]] = []
        for child in sorted(path.iterdir(), key=lambda item: item.name.lower()):
            if not self.policy.allows_for_scan(child):
                continue
            entries.append({
                "path": child.relative_to(self.policy.root).as_posix(),
                "type": "directory" if child.is_dir() else "file",
            })
            if len(entries) >= _MAX_LIST_ENTRIES:
                break
        return {"entries": entries, "truncated": len(entries) >= _MAX_LIST_ENTRIES}

    def _read_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self.policy.resolve(self._string(arguments, "path"))
        if not path.is_file():
            raise ValueError("path is not a file")
        if path.stat().st_size > _MAX_READ_BYTES:
            raise ValueError(f"file exceeds {_MAX_READ_BYTES} bytes")
        start = self._positive_int(arguments.get("start_line", 1), "start_line")
        end = self._positive_int(arguments.get("end_line", 200), "end_line")
        if end < start or end - start > 999:
            raise ValueError("line range must be ordered and at most 1000 lines")
        lines = path.read_text(encoding="utf-8").splitlines()
        selected = lines[start - 1 : end]
        numbered = "\n".join(f"{number}: {line}" for number, line in enumerate(selected, start=start))
        return {
            "path": path.relative_to(self.policy.root).as_posix(),
            "start_line": start,
            "end_line": start + len(selected) - 1,
            "content": redact_text(numbered),
        }

    def _search_text(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = self._string(arguments, "query")
        if len(query) > 500:
            raise ValueError("query is too long")
        root = self.policy.resolve(arguments.get("path", "."))
        paths = [root] if root.is_file() else self._walk_files(root)
        matches: list[dict[str, Any]] = []
        scanned = 0
        for path in paths:
            if scanned >= _MAX_SCAN_FILES or len(matches) >= _MAX_SEARCH_MATCHES:
                break
            scanned += 1
            try:
                if path.stat().st_size > _MAX_READ_BYTES:
                    continue
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                    if query in line:
                        matches.append({
                            "path": path.relative_to(self.policy.root).as_posix(),
                            "line": number,
                            "text": redact_text(line),
                        })
                        if len(matches) >= _MAX_SEARCH_MATCHES:
                            break
            except (OSError, UnicodeError):
                continue
        return {
            "matches": matches,
            "files_scanned": scanned,
            "truncated": scanned >= _MAX_SCAN_FILES or len(matches) >= _MAX_SEARCH_MATCHES,
        }

    def _edit_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self.policy.resolve(self._string(arguments, "path"))
        if not path.is_file():
            raise ValueError("path is not a file")
        old_text = self._string(arguments, "old_text", allow_empty=False)
        new_text = self._string(arguments, "new_text", allow_empty=True)
        original = path.read_text(encoding="utf-8")
        if original.count(old_text) != 1:
            raise ValueError("old_text must occur exactly once")
        updated = original.replace(old_text, new_text, 1)
        return self._approved_write(path, original, updated)

    def _write_file(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = self.policy.resolve(self._string(arguments, "path"), must_exist=False)
        if not path.parent.is_dir():
            raise ValueError("parent directory does not exist")
        original = path.read_text(encoding="utf-8") if path.exists() else ""
        content = self._string(arguments, "content", allow_empty=True)
        return self._approved_write(path, original, content)

    def _approved_write(self, path: Path, original: str, updated: str) -> dict[str, Any]:
        relative = path.relative_to(self.policy.root).as_posix()
        diff = "".join(difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        ))
        if len(diff) > _MAX_TOOL_OUTPUT:
            raise ValueError(
                f"diff exceeds {_MAX_TOOL_OUTPUT} characters; split the change into smaller edits"
            )
        preview = redact_text(diff)
        if not self.policy.confirm_mutation(f"Proposed change to {relative}:\n{preview}\nApply? [y/N] "):
            return {"path": relative, "applied": False, "reason": "user declined"}
        mode = path.stat().st_mode if path.exists() else None
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(updated)
                handle.flush()
                os.fsync(handle.fileno())
            if mode is not None:
                os.chmod(temporary_name, mode)
            os.replace(temporary_name, path)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return {"path": relative, "applied": True, "bytes": len(updated.encode("utf-8"))}

    def _walk_files(self, root: Path) -> list[Path]:
        files: list[Path] = []
        for current, directory_names, file_names in os.walk(root):
            current_path = Path(current)
            directory_names[:] = [
                name for name in directory_names if self.policy.allows_for_scan(current_path / name)
            ]
            for name in file_names:
                path = current_path / name
                if self.policy.allows_for_scan(path):
                    files.append(path)
                    if len(files) >= _MAX_SCAN_FILES:
                        return files
        return files

    @staticmethod
    def _string(arguments: dict[str, Any], name: str, *, allow_empty: bool = False) -> str:
        value = arguments.get(name)
        if not isinstance(value, str) or (not allow_empty and not value):
            raise TypeError(f"{name} must be a string")
        return value

    @staticmethod
    def _positive_int(value: Any, name: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise TypeError(f"{name} must be a positive integer")
        return value

    @staticmethod
    def _result(ok: bool, **payload: Any) -> str:
        text = redact_text(
            json.dumps({"ok": ok, **payload}, ensure_ascii=False, separators=(",", ":"))
        )
        if len(text) > _MAX_TOOL_OUTPUT:
            return json.dumps({
                "ok": False,
                "error": f"tool output exceeds {_MAX_TOOL_OUTPUT} characters; narrow the request",
            }, separators=(",", ":"))
        return text
