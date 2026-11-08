
"""Append-only audit log: one JSON object per line (JSON Lines).

This module imports nothing from the gateway or the policy. The gateway decides
what an audit failure means (e.g. "do not run the tool").
"""
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

OUTCOMES = frozenset({"allowed", "ok", "error", "blocked"})

MAX_FIELD_CHARS = 200
MAX_DETAIL_CHARS = 300
MAX_ARGS_CHARS = 500
MAX_ENTRY_CHARS = 16_384
_SCAN_CHARS = 1000
_MAX_NODES = 1000
_MAX_DEPTH = 10

SENSITIVE_KEYS = (
    "password", "passwd", "passphrase", "secret", "token", "apikey",
    "accesskey", "privatekey", "authorization", "cookie", "credential",
    "sessionid"
)

_SEPARATORS = re.compile(r"[-_\s]")

_SECRET_PATTERNS = [
    (
        re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@"),
        r"\1[REDACTED]@"
    ),
    (
        re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}"),
        r"\1 [REDACTED]"
    ),
    (
        re.compile(
            r"(?i)((?:password|passwd|passphrase|secret|token|api[_-]?key|access[_-]?key"
            r"|private[_-]?key|credential|session[_-]?id|authorization|cookie)[\w-]*"
            r"\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^\s,;&]+)"
        ),
        r"\1[REDACTED]"
    ),
    (
        re.compile(
            r"\b(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
            r"|xox[baprs]-[A-Za-z0-9-]{10,})"
        ),
        "[REDACTED]"
    ),
]


def _clip(text, limit):
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _scrub(text):
    text = _clip(text, _SCAN_CHARS)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _text(value, limit=MAX_FIELD_CHARS):
    if isinstance(value, str):
        s = _scrub(value)
    elif value is None or isinstance(value, (bool, int, float)):
        s = str(value)
    else:
        s = f"<{type(value).__name__}>"
    return _clip(s, limit)


def _key_is_sensitive(raw):
    if isinstance(raw, str):
        if len(raw) > _SCAN_CHARS:
            return True
        return any(
            s in _SEPARATORS.sub("", raw.lower())
            for s in SENSITIVE_KEYS
        )
    return not (raw is None or isinstance(raw, (bool, int, float)))


def _unique(taken, key):
    candidate, n = key, 2
    while candidate in taken:
        candidate = f"{key}#{n}"
        n += 1
    return candidate


def _redact_dict(value, state, depth):
    out = {}
    for raw in value:
        if state["nodes"] <= 0:
            out["[...]"] = "more items not shown"
            break

        name = _unique(out, _text(raw, 100))

        if _key_is_sensitive(raw):
            out[name] = "[REDACTED]"
        else:
            out[name] = _redact(value[raw], state, depth + 1)

    return out


def _redact(value, _state=None, _depth=0):
    state = _state if _state is not None else {
        "nodes": _MAX_NODES,
        "path": set()
    }

    state["nodes"] -= 1

    if state["nodes"] < 0:
        return "[...]"

    if _depth > _MAX_DEPTH:
        return "[too deep]"

    if isinstance(value, str):
        return _scrub(value)

    if value is None or isinstance(value, (bool, int, float)):
        return value

    if not isinstance(value, (dict, list, tuple, set, frozenset)):
        return f"<{type(value).__name__}>"

    if id(value) in state["path"]:
        return "[circular]"

    state["path"].add(id(value))

    try:
        if isinstance(value, dict):
            return _redact_dict(value, state, _depth)

        items = []

        for item in value:
            if state["nodes"] <= 0:
                items.append("[...]")
                break

            items.append(_redact(item, state, _depth + 1))

        if isinstance(value, (set, frozenset)):
            items.sort(key=repr)

        return items

    finally:
        state["path"].discard(id(value))


def _summarize_args(args):
    try:
        safe = _redact(args)
        text = json.dumps(safe)
    except Exception:
        return {"unserializable": True}

    if len(text) <= MAX_ARGS_CHARS:
        return safe

    return {
        "truncated": True,
        "chars": len(text),
        "preview": text[:MAX_ARGS_CHARS]
    }


class AuditLog:
    def __init__(self, path=None, clock=None):
        if clock is not None and not callable(clock):
            raise ValueError("clock must be a function that returns a datetime")

        if path is None:
            path = os.environ.get("AGENT_AUDIT_LOG") or "audit.jsonl"

        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._clock = (
            clock if clock is not None
            else lambda: datetime.now(timezone.utc)
        )

        self._lock = threading.Lock()

    def _now(self):
        now = self._clock()

        if not isinstance(now, datetime):
            raise ValueError(
                f"clock must return a datetime, got {type(now).__name__}"
            )

        if now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")

        return now.astimezone(timezone.utc)

    def _open_for_append(self):
        """Open the audit file with owner-only permissions where supported."""
        flags = (
            os.O_WRONLY
            | os.O_APPEND
            | os.O_CREAT
            | getattr(os, "O_BINARY", 0)
        )

        fd = os.open(self.path, flags, 0o600)

        try:
            # Restrict permissions even if the file already existed.
            if os.name != "nt" and hasattr(os, "fchmod"):
                os.fchmod(fd, 0o600)

            return os.fdopen(
                fd,
                "a",
                encoding="utf-8",
                newline="\n"
            )

        except Exception:
            os.close(fd)
            raise

    def write(
        self,
        *,
        call_id,
        tool,
        principal,
        risk,
        outcome,
        args,
        detail=""
    ):
        if not isinstance(outcome, str) or outcome not in OUTCOMES:
            raise ValueError(
                f"unknown outcome {outcome!r}, choose from {sorted(OUTCOMES)}"
            )

        entry = {
            "ts": self._now().isoformat(),
            "call_id": _text(call_id),
            "principal": _text(principal),
            "tool": _text(tool),
            "risk": _text(risk),
            "outcome": outcome,
            "detail": _text(detail, MAX_DETAIL_CHARS),
            "args": _summarize_args(args),
        }

        line = json.dumps(entry) + "\n"

        # Enforce the maximum serialized entry size before writing.
        if len(line.rstrip("\n")) > MAX_ENTRY_CHARS:
            raise ValueError(
                f"audit entry exceeds maximum size of {MAX_ENTRY_CHARS} characters"
            )

        with self._lock, self._open_for_append() as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def read(self, *, strict=False):
        with self._lock:
            if not self.path.exists():
                return []

            text = self.path.read_text(encoding="utf-8")

        lines = [line for line in text.split("\n") if line.strip()]
        entries = []

        for i, line in enumerate(lines):
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                if i == len(lines) - 1 and not strict:
                    break
                raise

        return entries


audit_log = AuditLog()
