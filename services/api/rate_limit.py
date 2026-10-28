"""Small process-local fixed-window guard for costly model entry points.

Production deployments should place a distributed limiter at the gateway as
well. This application-layer check remains useful because it keys on the
authenticated principal rather than a shared NAT address.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, status

_attempts: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(1, value)


def enforce_model_rate_limit(principal: str) -> None:
    """Reject a principal after the configured number of model calls/window."""
    limit = _positive_int("AGENT_RATE_LIMIT_REQUESTS", 20)
    window = _positive_int("AGENT_RATE_LIMIT_WINDOW_SECONDS", 60)
    now = time.monotonic()
    key = f"agent-query:{principal}"
    with _lock:
        bucket = _attempts[key]
        cutoff = now - window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry_after = max(1, int(window - (now - bucket[0])))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Support-agent request limit reached. Please try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)


def reset_rate_limits() -> None:
    """Clear process state for deterministic tests."""
    with _lock:
        _attempts.clear()
