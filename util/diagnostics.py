"""Lightweight, rate-limited diagnostics for otherwise-silent exception handlers.

Motivation: the codebase has many `except Exception: pass` sites. Most are
legitimate fallbacks (GUI input coercion, teardown best-effort, draining a
queue). A minority sit on initialization and resource-cleanup paths, where a
swallowed failure leaves no trace and makes field diagnosis impossible.

`note_suppressed` is for those. It reports each distinct site at most
`_MAX_REPEATS` times so a failure inside a loop or a per-frame callback cannot
flood stderr, which is exactly why those handlers were silenced originally.

Kept deliberately dependency-free: this module is imported by core mix-ins that
must not gain new third-party requirements.
"""
import os
import sys
import threading

# Opt-out for release builds / benchmarking.
_ENABLED = os.environ.get("DOPA_DIAG_SUPPRESSED", "1") not in ("0", "false", "False")
_MAX_REPEATS = 3

_lock = threading.Lock()
_seen: dict[str, int] = {}


def note_suppressed(where: str, exc: BaseException) -> None:
    """Report a swallowed exception once per site (up to _MAX_REPEATS).

    `where` should identify the call site, e.g. "_secure_cleanup/cuda-ctx".
    Never raises: a diagnostic must not become the failure it is reporting.
    """
    if not _ENABLED:
        return
    try:
        with _lock:
            n = _seen.get(where, 0)
            if n >= _MAX_REPEATS:
                return
            _seen[where] = n + 1
            last = " (further occurrences suppressed)" if n + 1 == _MAX_REPEATS else ""
        print(f"[diag] suppressed in {where}: {type(exc).__name__}: {exc}{last}",
              file=sys.stderr)
    except Exception:
        # Diagnostics are strictly best-effort.
        pass


def suppressed_summary() -> dict[str, int]:
    """Snapshot of site -> observed count. Intended for tests and teardown logs."""
    with _lock:
        return dict(_seen)


def reset_suppressed() -> None:
    """Clear recorded sites. Test-support only."""
    with _lock:
        _seen.clear()
