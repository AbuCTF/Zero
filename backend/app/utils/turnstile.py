"""
Cloudflare Turnstile server-side verification.

Verifies a Turnstile token against Cloudflare's siteverify endpoint before a
protected action runs. When Turnstile is disabled (keys unset) this is a no-op,
so it is safe to call unconditionally.

Fails CLOSED on network/timeout error: if the token cannot be verified, the
request is rejected.
"""

import logging
from typing import Optional

import httpx
from fastapi import HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile(token: Optional[str], remote_ip: Optional[str] = None) -> None:
    """
    Verify a Cloudflare Turnstile token server-side.

    - No-op when ``settings.turnstile_enabled`` is False (keys not configured).
    - Raises ``HTTPException(400)`` when the token is missing.
    - POSTs form-encoded ``secret``/``response``/``remoteip`` to Cloudflare with a
      5-second timeout and raises ``HTTPException(400)`` if verification fails.
    - Fails closed on any network/timeout error (raises ``HTTPException(400)``).
    """
    if not settings.turnstile_enabled:
        return

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captcha verification failed",
        )

    payload = {
        "secret": settings.turnstile_secret_key,
        "response": token,
    }
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(SITEVERIFY_URL, data=payload)
            result = resp.json()
    except Exception as exc:  # noqa: BLE001 - fail closed on any network error
        logger.warning("Turnstile verification error (fail-closed): %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captcha verification failed",
        )

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captcha verification failed",
        )
