"""Workspace confinement and user approval policy."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Callable


class PolicyError(ValueError):
    """A requested operation violates the workspace policy."""


Confirm = Callable[[str], bool]


_BLOCKED_PARTS = frozenset({
    ".git",
    ".jj",
    ".ssh",
    ".gnupg",
    ".aws",
    ".kube",
    ".pithon",
    "credentials",
    "secrets",
})
_BLOCKED_NAMES = (
    ".env",
    ".env.*",
    "id_rsa*",
    "id_dsa*",
    "id_ecdsa*",
    "id_ed25519*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "*credentials*",
    "*secret*",
)


class WorkspacePolicy:
    """Confines tools to one root and blocks common credential locations."""

    def __init__(self, root: Path, confirm: Confirm) -> None:
        resolved = root.expanduser().resolve(strict=True)
        if not resolved.is_dir():
            raise PolicyError(f"workspace is not a directory: {resolved}")
        self.root = resolved
        self._confirm = confirm

    def resolve(self, relative: str, *, must_exist: bool = True) -> Path:
        if not isinstance(relative, str) or not relative.strip():
            raise PolicyError("path must be a non-empty string")
        candidate_input = Path(relative)
        if candidate_input.is_absolute():
            raise PolicyError("absolute paths are not allowed")
        if any(part == ".." for part in candidate_input.parts):
            raise PolicyError("parent traversal is not allowed")
        self._check_name(candidate_input)

        candidate = self.root.joinpath(candidate_input)
        self._reject_symlink_path(candidate)
        resolved = candidate.resolve(strict=must_exist)
        if not resolved.is_relative_to(self.root):
            raise PolicyError("path escapes the workspace")
        return resolved

    def confirm_mutation(self, summary: str) -> bool:
        return self._confirm(summary)

    def allows_for_scan(self, path: Path) -> bool:
        try:
            relative = path.relative_to(self.root)
            self._check_name(relative)
            self._reject_symlink_path(path)
            return True
        except (PolicyError, ValueError, OSError):
            return False

    @staticmethod
    def _check_name(relative: Path) -> None:
        lowered_parts = tuple(part.lower() for part in relative.parts)
        if any(part in _BLOCKED_PARTS for part in lowered_parts):
            raise PolicyError("path is in a blocked credential or metadata directory")
        for part in lowered_parts:
            if any(fnmatch.fnmatch(part, pattern) for pattern in _BLOCKED_NAMES):
                raise PolicyError("path name matches a blocked secret pattern")

    def _reject_symlink_path(self, candidate: Path) -> None:
        current = self.root
        try:
            parts = candidate.relative_to(self.root).parts
        except ValueError as error:
            raise PolicyError("path escapes the workspace") from error
        for part in parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise PolicyError("symlinks are not allowed")
