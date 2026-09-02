from __future__ import annotations

import re

_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|passwd|token|secret|api[_-]?key)\s*[=:]\s*\S+"),
    re.compile(r"(?i)(authorization:)\s*\S+"),
]


def truncate(text: str, max_bytes: int) -> str:
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return text
    return raw[:max_bytes].decode("utf-8", errors="replace") + "\n...[truncated]..."


def _redact_match(match: re.Match[str]) -> str:
    # Never use \\1 replacement strings: re.sub compiles them against the
    # pattern even when nothing matched, so a pattern without groups blows up.
    if match.lastindex:
        return f"{match.group(1)}=[REDACTED]"
    return "[REDACTED]"


def redact(text: str) -> str:
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(_redact_match, out)
    return out
