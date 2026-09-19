"""server-to-server identity provisioning for the anvil walk-in flow.

anvil calls this after it runs discord oauth itself and has a verified email.
it is the ONLY path that can create a pre-verified account (email walk-ins go
through the normal registration + verification mail instead), so it is locked
behind a shared api key. not rate-limited by ip on purpose: reveal-day bursts
all originate from anvil's single ip, so an ip limit would throttle legitimate
provisioning; the shared key is the control.
"""

import hmac
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.models import Event, Participant
from app.utils.security import hash_password

router = APIRouter()
settings = get_settings()


class ProvisionRequest(BaseModel):
    email: EmailStr | None = None
    email_verified: bool = False
    discord_id: str | None = None
    discord_username: str | None = None
    event_slug: str
    # login-only model: anvil sends create=false to look up an already-registered,
    # discord-linked participant (never creating one). create=true is legacy.
    create: bool = True


class ProvisionResponse(BaseModel):
    participant_id: str
    email: str
    username: str
    email_verified: bool
    created: bool


def require_anvil_key(x_anvil_api_key: str | None = Header(default=None)) -> None:
    expected = settings.anvil_zp_api_key
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Identity provisioning is not configured",
        )
    if not x_anvil_api_key or not hmac.compare_digest(x_anvil_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


@router.post(
    "/provision",
    response_model=ProvisionResponse,
    dependencies=[Depends(require_anvil_key)],
)
async def provision_identity(
    data: ProvisionRequest,
    db: AsyncSession = Depends(get_session),
):
    result = await db.execute(select(Event).where(Event.slug == data.event_slug))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if not data.create:
        # login-only: look up an already-registered, discord-linked participant.
        # never creates — a miss means "register at 2026.h7tex.com first".
        if not data.discord_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="discord_id is required for lookup",
            )
        result = await db.execute(
            select(Participant).where(
                Participant.event_id == event.id,
                Participant.extra_data["discord_id"].astext == data.discord_id,
            )
        )
        participant = result.scalar_one_or_none()
        if participant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No registered participant for this Discord account",
            )
        return ProvisionResponse(
            participant_id=str(participant.id),
            email=participant.email,
            username=participant.username or participant.email.split("@")[0],
            email_verified=participant.email_verified,
            created=False,
        )

    if not data.email:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="email is required to provision",
        )
    email = data.email.lower()

    result = await db.execute(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.email == email,
        )
    )
    participant = result.scalar_one_or_none()
    created = False

    if participant is None:
        base = (email.split("@")[0] or "player").lower()
        username = base
        counter = 1
        while True:
            exists = await db.execute(
                select(Participant.id).where(
                    Participant.event_id == event.id,
                    Participant.username == username,
                )
            )
            if exists.scalar_one_or_none() is None:
                break
            username = f"{base}{counter}"
            counter += 1

        extra: dict = {"source_channel": "anvil-walk-in"}
        if data.discord_id:
            extra["discord_id"] = data.discord_id
        if data.discord_username:
            extra["discord_username"] = data.discord_username[:64]

        participant = Participant(
            event_id=event.id,
            email=email,
            username=username,
            password_hash=hash_password(secrets.token_urlsafe(16)),
            name=(data.discord_username or base)[:255],
            email_verified=bool(data.email_verified),
            email_verified_at=datetime.now(timezone.utc) if data.email_verified else None,
            source="anvil-walk-in",
            extra_data=extra,
        )
        db.add(participant)
        await db.flush()
        created = True
    else:
        # returning or cross-method: anvil's discord verification upgrades an
        # unverified account, and links the discord id if not already set.
        if data.email_verified and not participant.email_verified:
            participant.email_verified = True
            participant.email_verified_at = datetime.now(timezone.utc)
        if data.discord_id and not (participant.extra_data or {}).get("discord_id"):
            extra = dict(participant.extra_data or {})
            extra["discord_id"] = data.discord_id
            if data.discord_username:
                extra["discord_username"] = data.discord_username[:64]
            participant.extra_data = extra
        await db.flush()

    return ProvisionResponse(
        participant_id=str(participant.id),
        email=participant.email,
        username=participant.username or email.split("@")[0],
        email_verified=participant.email_verified,
        created=created,
    )
