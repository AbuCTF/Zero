"""
Redis-backed IP rate limiting.

Provides a fixed-window limiter and a FastAPI dependency factory. Each generated
dependency keys on the client IP plus a scope string, INCRs Redis counters of the
form ``rl:{scope}:{ip}:{window}`` (with an EXPIRE on first increment), and raises
``HTTPException(429)`` when a window's limit is exceeded.

Fails OPEN on any Redis error: the failure is logged and the request is allowed.
"""

import logging
import time
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import get_client_ip, get_redis

logger = logging.getLogger(__name__)


async def check_rate_limit(
    redis,
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> bool:
    """
    Fixed-window rate-limit check.

    Increments the counter for the current window and returns ``True`` if the
    request is within the limit, ``False`` if it has been exceeded.

    Fails open (returns ``True``) on any Redis error.
    """
    if redis is None:
        return True

    try:
        window = int(time.time()) // window_seconds
        key = f"rl:{scope}:{identifier}:{window}"
        count = await redis.incr(key)
        if count == 1:
            # First hit in this window — set the TTL so the counter self-expires.
            await redis.expire(key, window_seconds)
        return count <= limit
    except Exception as exc:  # noqa: BLE001 - fail open on any Redis error
        logger.warning(
            "Rate limit check failed for scope=%s (fail-open): %s", scope, exc
        )
        return True


def rate_limit(scope: str, *limits: Tuple[int, int]):
    """
    FastAPI dependency factory.

    ``scope`` is a short label distinguishing the counter namespace (e.g.
    ``"auth:login"``). ``limits`` is one or more ``(max_requests, window_seconds)``
    pairs; every window is enforced and a 429 is raised if any is exceeded.

    Usage::

        @router.post("/login", dependencies=[Depends(rate_limit("auth:login", (10, 60)))])
    """
    windows = list(limits)

    async def dependency(request: Request, redis=Depends(get_redis)) -> None:
        identifier = get_client_ip(request) or "unknown"
        for max_requests, window_seconds in windows:
            allowed = await check_rate_limit(
                redis, scope, identifier, max_requests, window_seconds
            )
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests — slow down",
                )

    return dependency
