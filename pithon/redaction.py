"""Best-effort redaction for provider-bound text and local diagnostics.

Redaction is defense in depth. Path policy and user approval are the security
boundary; no regular expression can identify every secret.
"""

from __future__ import annotations

import re

_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_TOKEN = re.compile(
    r"(?<![A-Za-z0-9])(?:sk-[A-Za-z0-9_-]{16,}|gh[opusr]_[A-Za-z0-9_]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|AIza[A-Za-z0-9_-]{20,}|ek-[A-Za-z0-9_-]{16,})"
)
_ASSIGNMENT = re.compile(
    r"(?im)\b([A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)"
    r"(\s*[:=]\s*)(['\"]?)([^\s'\"]{8,})(['\"]?)"
)
_JWT = re.compile(r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")


def redact_text(text: str) -> str:
    """Replace common credential forms without claiming perfect detection."""

    text = _PRIVATE_KEY.sub("<redacted-private-key>", text)
    text = _TOKEN.sub("<redacted-token>", text)
    text = _JWT.sub("<redacted-jwt>", text)
    return _ASSIGNMENT.sub(lambda match: f"{match.group(1)}{match.group(2)}<redacted>", text)
