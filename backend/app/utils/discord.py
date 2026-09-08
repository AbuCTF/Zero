"""
Discord OAuth2 helpers for participant identity verification.

Flow: the registration popup opens ``/api/auth/discord/authorize`` (which redirects to
Discord); Discord redirects back to ``/api/auth/discord/callback``, which exchanges the
code server-side (using the client secret), verifies the account meets the minimum age,
and hands the popup a short-lived signed "discord-verified" token via ``postMessage``.
The register endpoint then trusts that token to attach the verified Discord identity.

The client secret never leaves the server. Only the ``identify`` scope is requested, and
account age is derived from the Discord snowflake id (no extra scope needed).
"""

import json
import logging
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.utils.security import generate_timed_token, verify_timed_token

logger = logging.getLogger(__name__)
settings = get_settings()

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
USER_URL = "https://discord.com/api/users/@me"
DISCORD_EPOCH_MS = 1420070400000

_STATE_PURPOSE = "discord_state"
_VERIFY_PURPOSE = "discord_verify"


def _pack(purpose: str, obj: dict, ttl: timedelta) -> str:
    """Sign a small payload into a URL-safe timed token (base64 so it never contains '|')."""
    raw = json.dumps({"p": purpose, **obj}, separators=(",", ":"))
    data = urlsafe_b64encode(raw.encode()).decode()
    return generate_timed_token(data, ttl)


def _unpack(purpose: str, token: str) -> Optional[dict]:
    ok, data = verify_timed_token(token)
    if not ok or not data:
        return None
    try:
        obj = json.loads(urlsafe_b64decode(data.encode()).decode())
    except Exception:
        return None
    return obj if obj.get("p") == purpose else None


def popup_origin_allowed(origin: str) -> bool:
    allowed = [o.strip() for o in settings.discord_popup_origins.split(",") if o.strip()]
    return origin in allowed


def make_state(origin: str) -> str:
    return _pack(_STATE_PURPOSE, {"o": origin}, timedelta(minutes=10))


def read_state(state: str) -> Optional[str]:
    obj = _unpack(_STATE_PURPOSE, state)
    return obj.get("o") if obj else None


def build_authorize_url(state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": settings.discord_client_id,
        "scope": "identify",
        "redirect_uri": settings.discord_redirect_uri,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def account_age_days(discord_id: str) -> Optional[float]:
    """Derive account age (days) from the Discord snowflake id."""
    try:
        created_ms = (int(discord_id) >> 22) + DISCORD_EPOCH_MS
    except (ValueError, TypeError):
        return None
    return (time.time() * 1000 - created_ms) / 86_400_000.0


async def exchange_code(code: str) -> Optional[dict]:
    """Exchange an authorization code for the Discord user object; None on any failure."""
    data = {
        "client_id": settings.discord_client_id,
        "client_secret": settings.discord_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.discord_redirect_uri,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            tok = await client.post(
                TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if tok.status_code != 200:
                logger.warning("Discord token exchange failed: %s %s", tok.status_code, tok.text[:200])
                return None
            access_token = tok.json().get("access_token")
            if not access_token:
                return None
            usr = await client.get(USER_URL, headers={"Authorization": f"Bearer {access_token}"})
            if usr.status_code != 200:
                logger.warning("Discord /users/@me failed: %s", usr.status_code)
                return None
            return usr.json()
    except Exception as exc:  # noqa: BLE001 - network/parse failures -> treat as failed verification
        logger.warning("Discord exchange error: %s", exc)
        return None


def issue_verify_token(discord_id: str, username: str, global_name: Optional[str]) -> str:
    return _pack(
        _VERIFY_PURPOSE,
        {"id": str(discord_id), "u": username or "", "g": global_name or ""},
        timedelta(minutes=20),
    )


def read_verify_token(token: str) -> Optional[dict]:
    """Return {id, u, g} for a valid discord-verify token, else None."""
    return _unpack(_VERIFY_PURPOSE, token)


def result_html(origin: str, payload: dict) -> str:
    """A tiny page that postMessages the result to the popup opener, then closes itself."""
    data = json.dumps(payload)
    target = json.dumps(origin)  # JSON-quoted: an exact origin, or "*" for the un-validated error case
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><title>Discord verification</title></head>"
        "<body style=\"font-family:system-ui,-apple-system,sans-serif;background:#0b0b0e;color:#e5e5e5;"
        "display:flex;align-items:center;justify-content:center;height:100vh;margin:0\">"
        "<p>Finishing Discord verification — you can close this window.</p>"
        "<script>(function(){var payload=" + data + ";"
        "try{if(window.opener)window.opener.postMessage(payload," + target + ");}catch(e){}"
        "setTimeout(function(){try{window.close();}catch(e){}},300);})();</script>"
        "</body></html>"
    )
