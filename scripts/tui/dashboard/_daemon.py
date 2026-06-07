from __future__ import annotations

import logging
from typing import Any

import loopback_http

log = logging.getLogger("flowkey.tui.dashboard")

DAEMON_BASE_URL = "http://127.0.0.1:52650"
REFRESH_INTERVAL = 10.0  # seconds between auto-refresh

# ---------------------------------------------------------------------------
# Data fetcher helpers
# ---------------------------------------------------------------------------

_DAEMON_TIMEOUT_DEFAULT = 5.0
_DAEMON_TIMEOUT_MODEL_CHANGE = 75.0  # Must accommodate: stop_flm (~3s) + start_flm port-poll (up to 25s) + warmup request (up to 30s) + buffer
_DAEMON_TIMEOUT_PULL_START = 25.0
_DAEMON_TIMEOUT_PULL_CANCEL = 10.0


def _daemon_post(action: str, args: dict | None = None, *, timeout: float = _DAEMON_TIMEOUT_DEFAULT) -> dict:
    """POST to daemon action and return parsed response."""
    try:
        return loopback_http.json_post(
            f"{DAEMON_BASE_URL}/action/{action}",
            {"args": args or {}},
            headers=loopback_http.daemon_headers(),
            timeout=timeout,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _resolve_result(resp: dict) -> Any:
    """Extract result from daemon response, or error string."""
    if resp.get("ok"):
        return resp.get("result")
    return f"Error: {resp.get('error', 'unknown')}"
