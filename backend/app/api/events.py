"""
Events API Routes

Public event information endpoints.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_redis
from app.config import get_settings
from app.database import get_session
from app.models import Event, EventStatus, Participant, EmailProvider, User
from app.schemas import EventListResponse, EventResponse
from app.services.email import EmailMessage, EmailOrchestrator, render_email, render_subject
from app.utils.security import hash_password
import secrets

router = APIRouter()
settings = get_settings()


@router.get("", response_model=EventListResponse)
async def list_events(
    status_filter: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_session),
):
    """
    List public events.
    
    Only shows events with status 'registration' or 'live'.
    """
    query = select(Event).where(
        Event.status.in_([EventStatus.REGISTRATION, EventStatus.LIVE])
    )
    
    if status_filter:
        try:
            status_enum = EventStatus(status_filter)
            query = query.where(Event.status == status_enum)
        except ValueError:
            pass
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Paginate
    query = query.order_by(Event.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    # Get participant counts
    event_responses = []
    for event in events:
        participant_count_result = await db.execute(
            select(func.count()).where(Participant.event_id == event.id)
        )
        participant_count = participant_count_result.scalar() or 0
        
        verified_count_result = await db.execute(
            select(func.count()).where(
                Participant.event_id == event.id,
                Participant.email_verified == True,
            )
        )
        verified_count = verified_count_result.scalar() or 0
        
        event_responses.append(
            EventResponse(
                id=event.id,
                name=event.name,
                slug=event.slug,
                description=event.description,
                status=event.status.value,
                registration_start=event.registration_start,
                registration_end=event.registration_end,
                event_start=event.event_start,
                event_end=event.event_end,
                ctfd_url=event.ctfd_url,
                ctfd_synced_at=event.ctfd_synced_at,
                settings=event.settings,
                created_at=event.created_at,
                participant_count=participant_count,
                verified_count=verified_count,
                is_import_only=event.settings.get("is_import_only", False) if event.settings else False,
                team_mode=event.settings.get("team_mode", False) if event.settings else False,
            )
        )
    
    pages = (total + per_page - 1) // per_page
    
    return EventListResponse(
        success=True,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        events=event_responses,
    )


@router.get("/{slug}", response_model=EventResponse)
async def get_event(
    slug: str,
    db: AsyncSession = Depends(get_session),
):
    """Get event by slug."""
    result = await db.execute(
        select(Event).where(Event.slug == slug.lower())
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    # Get participant counts
    participant_count_result = await db.execute(
        select(func.count()).where(Participant.event_id == event.id)
    )
    participant_count = participant_count_result.scalar() or 0
    
    verified_count_result = await db.execute(
        select(func.count()).where(
            Participant.event_id == event.id,
            Participant.email_verified == True,
        )
    )
    verified_count = verified_count_result.scalar() or 0
    
    return EventResponse(
        id=event.id,
        name=event.name,
        slug=event.slug,
        description=event.description,
        status=event.status.value,
        registration_start=event.registration_start,
        registration_end=event.registration_end,
        event_start=event.event_start,
        event_end=event.event_end,
        ctfd_url=event.ctfd_url,
        ctfd_synced_at=event.ctfd_synced_at,
        settings=event.settings,
        created_at=event.created_at,
        participant_count=participant_count,
        verified_count=verified_count,
        is_import_only=event.settings.get("is_import_only", False) if event.settings else False,
        team_mode=event.settings.get("team_mode", False) if event.settings else False,
    )


# Registration request schema
class ParticipantRegistrationRequest(BaseModel):
    """Participant registration request."""
    name: str
    email: EmailStr
    team_name: Optional[str] = None
    team_password: Optional[str] = None


class RegistrationResponse(BaseModel):
    """Registration response."""
    success: bool
    message: str
    participant_id: Optional[UUID] = None


@router.post("/{event_id}/register", response_model=RegistrationResponse)
async def register_for_event(
    event_id: UUID,
    data: ParticipantRegistrationRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """
    Register a participant for an event.
    
    This is the public registration endpoint.
    """
    # Get event
    result = await db.execute(
        select(Event).where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    # Check if import-only mode
    settings = event.settings or {}
    if settings.get("is_import_only", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This event does not accept public registration",
        )
    
    # Check event status
    if event.status not in [EventStatus.REGISTRATION, EventStatus.LIVE]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration is not open for this event",
        )
    
    # Check registration window
    now = datetime.now(timezone.utc)
    if event.registration_start and event.registration_start > now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration has not started yet",
        )
    if event.registration_end and event.registration_end < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration has ended",
        )
    
    # Check max participants
    if settings.get("max_participants"):
        count_result = await db.execute(
            select(func.count()).where(Participant.event_id == event_id)
        )
        current_count = count_result.scalar() or 0
        if current_count >= settings["max_participants"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event has reached maximum capacity",
            )
    
    # Block organizer/admin emails from registering as participants
    admin_check = await db.execute(
        select(User).where(User.email == data.email.lower())
    )
    if admin_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organizer accounts cannot register as participants",
        )

    # Check if email already registered
    existing = await db.execute(
        select(Participant).where(
            Participant.event_id == event_id,
            Participant.email == data.email.lower(),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email is already registered for this event",
        )
    
    # Generate username from email
    username = data.email.split("@")[0].lower()
    base_username = username
    counter = 1
    while True:
        check_result = await db.execute(
            select(Participant).where(
                Participant.event_id == event_id,
                Participant.username == username,
            )
        )
        if not check_result.scalar_one_or_none():
            break
        username = f"{base_username}{counter}"
        counter += 1
    
    # Generate password
    password = secrets.token_urlsafe(10)
    
    # Get client IP
    client_ip = request.client.host if request.client else None
    
    # Create participant
    participant = Participant(
        event_id=event_id,
        email=data.email.lower(),
        username=username,
        password_hash=hash_password(password),
        name=data.name,
        registration_ip=client_ip,
        email_verified=False,
        source="registration",
        extra_data={
            "team_name": data.team_name,
        } if data.team_name else {},
    )
    
    db.add(participant)
    await db.flush()
    
    # Generate verification token
    verification_token = secrets.token_urlsafe(32)
    participant.email_verification_token = verification_token
    participant.email_verification_sent_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    # Send verification email
    await _send_registration_verification_email(
        db, redis, participant, event, verification_token
    )
    
    return RegistrationResponse(
        success=True,
        message="Registration successful! Please check your email to verify your account.",
        participant_id=participant.id,
    )


async def _send_registration_verification_email(
    db: AsyncSession,
    redis,
    participant: Participant,
    event: Event,
    verification_token: str,
):
    """Send verification email to newly registered participant."""
    # Get active providers
    result = await db.execute(
        select(EmailProvider).where(
            EmailProvider.is_active == True
        ).order_by(EmailProvider.priority)
    )
    providers = result.scalars().all()
    
    if not providers:
        # Log warning but don't fail registration
        print("Warning: No email providers configured - verification email not sent")
        return
    
    # Prepare provider configs
    provider_configs = [
        {
            "id": p.id,
            "name": p.name,
            "type": p.provider_type.value,
            "config": p.config,
            "priority": p.priority,
            "daily_limit": p.daily_limit,
            "hourly_limit": p.hourly_limit,
            "minute_limit": p.minute_limit,
            "second_limit": p.second_limit,
        }
        for p in providers
    ]
    
    # Render email
    from app.services.email.templates import DEFAULT_TEMPLATES
    
    verification_url = f"{settings.app_url}/verify?token={verification_token}"
    
    template = DEFAULT_TEMPLATES["verification"]
    variables = {
        "event_name": event.name,
        "username": participant.username,
        "verification_url": verification_url,
    }
    
    body_html, body_text = render_email(
        template["body_html"],
        variables,
        template["body_text"],
    )
    subject = render_subject(template["subject"], variables)
    
    # Create message
    message = EmailMessage(
        to=participant.email,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        participant_id=participant.id,
        template_slug="verification",
    )
    
    # Send via orchestrator
    orchestrator = EmailOrchestrator(redis)
    await orchestrator.send(message, provider_configs)
