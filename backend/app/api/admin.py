"""
Admin API Routes

Comprehensive admin endpoints for managing:
- Events
- Participants
- Email providers
- Email templates
- Voucher pools
- Prize rules
- Certificate templates
- Campaigns
- Analytics
"""

import csv
import io
import secrets
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, get_redis, require_admin, require_organizer
from app.config import get_settings
from app.database import get_session
from app.models import (
    AuditLog,
    Certificate,
    CertificateTemplate,
    EmailCampaign,
    EmailLog,
    EmailProvider,
    EmailStatus,
    EmailTemplate,
    Event,
    EventStatus,
    Participant,
    Prize,
    PrizeRule,
    PrizeStatus,
    ProviderType,
    Team,
    TeamMember,
    User,
    Voucher,
    VoucherPool,
    VoucherStatus,
)
from app.schemas import (
    BaseResponse,
    CampaignCreate,
    CampaignResponse,
    CertificateTemplateCreate,
    CertificateTemplateResponse,
    CertificateTemplateUpdate,
    DashboardStats,
    EmailProviderCreate,
    EmailProviderResponse,
    EmailProviderTestRequest,
    EmailProviderTestResponse,
    EmailProviderUpdate,
    EmailTemplateCreate,
    EmailTemplateResponse,
    EmailTemplateUpdate,
    EventCreate,
    EventListResponse,
    EventResponse,
    EventStats,
    EventUpdate,
    ParticipantBulkRankUpdate,
    ParticipantImportRequest,
    ParticipantImportResponse,
    ParticipantListResponse,
    ParticipantResponse,
    ParticipantUpdate,
    PrizeRuleCreate,
    PrizeRuleResponse,
    VoucherPoolCreate,
    VoucherPoolResponse,
    VoucherUploadRequest,
)
from app.services.email import EmailMessage, EmailOrchestrator
from app.utils.security import encrypt_data, hash_password

router = APIRouter()
settings = get_settings()


def get_template_background_url(template_file: str) -> Optional[str]:
    """Convert template file path to accessible URL."""
    if not template_file:
        return None
    # template_file is like /app/storage/uploads/certificate-templates/{id}.png
    # We need to return /uploads/certificate-templates/{id}.png
    if template_file.startswith(settings.upload_dir):
        relative_path = template_file[len(settings.upload_dir):]
        if relative_path.startswith("/"):
            relative_path = relative_path[1:]
        return f"/uploads/{relative_path}"
    # If it's already a relative path, just prepend /uploads
    if not template_file.startswith("/"):
        return f"/uploads/{template_file}"
    return template_file


# =============================================================================
# Dashboard
# =============================================================================


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """Get dashboard statistics."""
    # Event counts
    total_events = await db.scalar(select(func.count()).select_from(Event))
    active_events = await db.scalar(
        select(func.count()).where(
            Event.status.in_([EventStatus.REGISTRATION, EventStatus.LIVE])
        )
    )
    
    # Participant counts
    total_participants = await db.scalar(select(func.count()).select_from(Participant))
    verified_participants = await db.scalar(
        select(func.count()).where(Participant.email_verified == True)
    )
    
    # Email counts
    total_emails = await db.scalar(select(func.count()).select_from(EmailLog))
    emails_today = await db.scalar(
        select(func.count()).where(
            EmailLog.sent_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
        )
    )
    
    # Certificate counts
    total_certs = await db.scalar(select(func.count()).select_from(Certificate))
    certs_downloaded = await db.scalar(
        select(func.count()).where(Certificate.downloaded_at.isnot(None))
    )
    
    # Prize counts
    total_prizes = await db.scalar(select(func.count()).select_from(Prize))
    prizes_claimed = await db.scalar(
        select(func.count()).where(Prize.status == PrizeStatus.CLAIMED)
    )
    
    # Provider stats
    providers_total = await db.scalar(select(func.count()).select_from(EmailProvider))
    providers_active = await db.scalar(
        select(func.count()).where(EmailProvider.is_active == True)
    )
    
    # Get daily email capacity
    result = await db.execute(
        select(func.sum(EmailProvider.daily_limit)).where(EmailProvider.is_active == True)
    )
    daily_capacity = result.scalar() or 0
    
    # Get today's usage from Redis
    daily_used = 0
    result = await db.execute(
        select(EmailProvider).where(EmailProvider.is_active == True)
    )
    providers = result.scalars().all()
    
    for p in providers:
        key = f"ratelimit:{p.id}:daily"
        used = await redis.get(key)
        daily_used += int(used) if used else 0
    
    return DashboardStats(
        total_events=total_events or 0,
        active_events=active_events or 0,
        total_participants=total_participants or 0,
        verified_participants=verified_participants or 0,
        total_emails_sent=total_emails or 0,
        emails_sent_today=emails_today or 0,
        total_certificates=total_certs or 0,
        certificates_downloaded=certs_downloaded or 0,
        total_prizes=total_prizes or 0,
        prizes_claimed=prizes_claimed or 0,
        providers_active=providers_active or 0,
        providers_total=providers_total or 0,
        daily_email_capacity=daily_capacity,
        daily_emails_used=daily_used,
    )


# =============================================================================
# Event Management
# =============================================================================


@router.get("/events", response_model=EventListResponse)
async def list_all_events(
    status_filter: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """List all events (admin view)."""
    query = select(Event)
    
    if status_filter:
        try:
            status_enum = EventStatus(status_filter)
            query = query.where(Event.status == status_enum)
        except ValueError:
            pass
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Paginate
    query = query.order_by(Event.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    event_responses = []
    for event in events:
        participant_count = await db.scalar(
            select(func.count()).where(Participant.event_id == event.id)
        )
        verified_count = await db.scalar(
            select(func.count()).where(
                Participant.event_id == event.id,
                Participant.email_verified == True,
            )
        )
        
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
                participant_count=participant_count or 0,
                verified_count=verified_count or 0,
                is_import_only=event.settings.get("is_import_only", False) if event.settings else False,
                team_mode=event.settings.get("team_mode", False) if event.settings else False,
            )
        )
    
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    return EventListResponse(
        success=True,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        events=event_responses,
    )


@router.post("/events", response_model=EventResponse)
async def create_event(
    data: EventCreate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Create a new event."""
    # Check slug uniqueness
    result = await db.execute(
        select(Event).where(Event.slug == data.slug.lower())
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Event slug already exists",
        )
    
    # Encrypt CTFd API key if provided
    ctfd_api_key = None
    if data.ctfd_api_key:
        ctfd_api_key = encrypt_data(data.ctfd_api_key)
    
    # Build settings from both settings dict and top-level fields
    event_settings = data.get_settings()
    
    event = Event(
        name=data.name,
        slug=data.slug.lower(),
        description=data.description,
        registration_start=data.get_registration_start(),
        registration_end=data.get_registration_end(),
        event_start=data.get_event_start(),
        event_end=data.get_event_end(),
        ctfd_url=data.ctfd_url,
        ctfd_api_key=ctfd_api_key,
        settings=event_settings,
        created_by=user.id,
    )
    
    db.add(event)
    await db.flush()
    
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
        is_import_only=event.settings.get("is_import_only", False) if event.settings else False,
        team_mode=event.settings.get("team_mode", False) if event.settings else False,
    )


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event_admin(
    event_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Get event details (admin view)."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    participant_count = await db.scalar(
        select(func.count()).where(Participant.event_id == event.id)
    )
    verified_count = await db.scalar(
        select(func.count()).where(
            Participant.event_id == event.id,
            Participant.email_verified == True,
        )
    )
    
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
        participant_count=participant_count or 0,
        verified_count=verified_count or 0,
        is_import_only=event.settings.get("is_import_only", False) if event.settings else False,
        team_mode=event.settings.get("team_mode", False) if event.settings else False,
    )


@router.patch("/events/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: UUID,
    data: EventUpdate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Update an event."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if data.name is not None:
        event.name = data.name
    if data.slug is not None:
        # Validate and normalize slug
        import re
        new_slug = re.sub(r'[^a-z0-9-]', '', data.slug.lower().replace(' ', '-'))
        if new_slug and new_slug != event.slug:
            # Check for uniqueness
            result = await db.execute(
                select(Event).where(Event.slug == new_slug, Event.id != event_id)
            )
            if result.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Slug already in use by another event")
            event.slug = new_slug
    if data.description is not None:
        event.description = data.description
    if data.registration_start is not None:
        event.registration_start = data.registration_start
    if data.registration_end is not None:
        event.registration_end = data.registration_end
    if data.event_start is not None:
        event.event_start = data.event_start
    if data.event_end is not None:
        event.event_end = data.event_end
    if data.status is not None:
        event.status = EventStatus(data.status)
    if data.ctfd_url is not None:
        event.ctfd_url = data.ctfd_url
    if data.ctfd_api_key is not None:
        event.ctfd_api_key = encrypt_data(data.ctfd_api_key)
    
    # Merge settings from both dict and top-level fields
    settings_update = data.settings.copy() if data.settings else {}
    if data.is_import_only is not None:
        settings_update["is_import_only"] = data.is_import_only
    if data.team_mode is not None:
        settings_update["team_mode"] = data.team_mode
    if data.max_participants is not None:
        settings_update["max_participants"] = data.max_participants
    if data.min_team_size is not None:
        settings_update["min_team_size"] = data.min_team_size
    if data.max_team_size is not None:
        settings_update["max_team_size"] = data.max_team_size
    
    if settings_update:
        event.settings = {**event.settings, **settings_update}
    
    await db.flush()
    
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
        is_import_only=event.settings.get("is_import_only", False) if event.settings else False,
        team_mode=event.settings.get("team_mode", False) if event.settings else False,
    )


@router.delete("/events/{event_id}", response_model=BaseResponse)
async def delete_event(
    event_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """
    Delete an event and all associated data.
    
    This is a destructive operation - only admins can perform it.
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Delete the event (cascades to participants, teams, etc.)
    await db.delete(event)
    await db.flush()
    
    return BaseResponse(success=True, message=f"Event '{event.name}' deleted successfully")


@router.get("/events/{event_id}/stats", response_model=EventStats)
async def get_event_stats(
    event_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Get detailed statistics for an event."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Participant stats
    participant_count = await db.scalar(
        select(func.count()).where(Participant.event_id == event_id)
    ) or 0
    
    verified_count = await db.scalar(
        select(func.count()).where(
            Participant.event_id == event_id,
            Participant.email_verified == True,
        )
    ) or 0
    
    ctfd_provisioned = await db.scalar(
        select(func.count()).where(
            Participant.event_id == event_id,
            Participant.ctfd_provisioned == True,
        )
    ) or 0
    
    team_count = await db.scalar(
        select(func.count()).where(Team.event_id == event_id)
    ) or 0
    
    # Email stats
    emails_sent = await db.scalar(
        select(func.count())
        .select_from(EmailLog)
        .join(Participant, EmailLog.participant_id == Participant.id)
        .where(Participant.event_id == event_id)
    ) or 0
    
    # Certificate stats
    certs_generated = await db.scalar(
        select(func.count())
        .select_from(Certificate)
        .join(Participant, Certificate.participant_id == Participant.id)
        .where(Participant.event_id == event_id)
    ) or 0
    
    certs_downloaded = await db.scalar(
        select(func.count())
        .select_from(Certificate)
        .join(Participant, Certificate.participant_id == Participant.id)
        .where(
            Participant.event_id == event_id,
            Certificate.downloaded_at.isnot(None),
        )
    ) or 0
    
    # Prize stats
    prizes_assigned = await db.scalar(
        select(func.count())
        .select_from(Prize)
        .join(Participant, Prize.participant_id == Participant.id)
        .where(Participant.event_id == event_id)
    ) or 0
    
    prizes_claimed = await db.scalar(
        select(func.count())
        .select_from(Prize)
        .join(Participant, Prize.participant_id == Participant.id)
        .where(
            Participant.event_id == event_id,
            Prize.status == PrizeStatus.CLAIMED,
        )
    ) or 0
    
    # Voucher stats
    vouchers_total = await db.scalar(
        select(func.count())
        .select_from(Voucher)
        .join(VoucherPool, Voucher.pool_id == VoucherPool.id)
        .where(VoucherPool.event_id == event_id)
    ) or 0
    
    vouchers_claimed = await db.scalar(
        select(func.count())
        .select_from(Voucher)
        .join(VoucherPool, Voucher.pool_id == VoucherPool.id)
        .where(
            VoucherPool.event_id == event_id,
            Voucher.status == VoucherStatus.CLAIMED,
        )
    ) or 0
    
    return EventStats(
        participant_count=participant_count,
        verified_count=verified_count,
        ctfd_provisioned_count=ctfd_provisioned,
        team_count=team_count,
        emails_sent=emails_sent,
        certificates_generated=certs_generated,
        certificates_downloaded=certs_downloaded,
        prizes_assigned=prizes_assigned,
        prizes_claimed=prizes_claimed,
        vouchers_total=vouchers_total,
        vouchers_claimed=vouchers_claimed,
    )


# =============================================================================
# Participant Management
# =============================================================================


@router.get("/events/{event_id}/participants", response_model=ParticipantListResponse)
async def list_participants(
    event_id: UUID,
    page: int = 1,
    per_page: int = 50,
    search: Optional[str] = None,
    verified: Optional[bool] = None,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """List participants for an event."""
    query = select(Participant).where(Participant.event_id == event_id)
    
    if search:
        query = query.where(
            (Participant.email.ilike(f"%{search}%")) |
            (Participant.username.ilike(f"%{search}%")) |
            (Participant.name.ilike(f"%{search}%"))
        )
    
    if verified is not None:
        query = query.where(Participant.email_verified == verified)
    
    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query) or 0
    
    # Paginate
    query = query.order_by(Participant.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    participants = result.scalars().all()
    
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    
    return ParticipantListResponse(
        success=True,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
        participants=[
            ParticipantResponse(
                id=p.id,
                email=p.email,
                username=p.username,
                name=p.name,
                email_verified=p.email_verified,
                email_verified_at=p.email_verified_at,
                ctfd_provisioned=p.ctfd_provisioned,
                ctfd_user_id=p.ctfd_user_id,
                final_rank=p.final_rank,
                final_score=p.final_score,
                is_blocked=p.is_blocked,
                source=p.source,
                created_at=p.created_at,
                extra_data=p.extra_data or {},
            )
            for p in participants
        ],
    )


@router.get("/participants/{participant_id}", response_model=ParticipantResponse)
async def get_participant(
    participant_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Get a single participant."""
    result = await db.execute(
        select(Participant).where(Participant.id == participant_id)
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    return ParticipantResponse(
        id=participant.id,
        email=participant.email,
        username=participant.username,
        name=participant.name,
        email_verified=participant.email_verified,
        email_verified_at=participant.email_verified_at,
        ctfd_provisioned=participant.ctfd_provisioned,
        ctfd_user_id=participant.ctfd_user_id,
        final_rank=participant.final_rank,
        final_score=participant.final_score,
        is_blocked=participant.is_blocked,
        source=participant.source,
        created_at=participant.created_at,
        extra_data=participant.extra_data or {},
    )


@router.patch("/participants/{participant_id}", response_model=ParticipantResponse)
async def update_participant(
    participant_id: UUID,
    data: ParticipantUpdate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Update a participant (name, rank, score, blocked status)."""
    result = await db.execute(
        select(Participant).where(Participant.id == participant_id)
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    if data.name is not None:
        participant.name = data.name
    if data.username is not None:
        participant.username = data.username
    if data.is_blocked is not None:
        participant.is_blocked = data.is_blocked
    if data.final_rank is not None:
        participant.final_rank = data.final_rank
    if data.final_score is not None:
        participant.final_score = data.final_score
    if data.metadata is not None:
        participant.extra_data = {**(participant.extra_data or {}), **data.metadata}
    
    await db.flush()
    
    return ParticipantResponse(
        id=participant.id,
        email=participant.email,
        username=participant.username,
        name=participant.name,
        email_verified=participant.email_verified,
        email_verified_at=participant.email_verified_at,
        ctfd_provisioned=participant.ctfd_provisioned,
        ctfd_user_id=participant.ctfd_user_id,
        final_rank=participant.final_rank,
        final_score=participant.final_score,
        is_blocked=participant.is_blocked,
        source=participant.source,
        created_at=participant.created_at,
        extra_data=participant.extra_data or {},
    )


@router.post("/events/{event_id}/participants/bulk-update-ranks", response_model=BaseResponse)
async def bulk_update_participant_ranks(
    event_id: UUID,
    data: ParticipantBulkRankUpdate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """
    Bulk update participant ranks/scores.
    
    Accepts: { participants: [{id: "uuid", final_rank: 1, final_score: 100}, ...] }
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Event not found")
    
    updated = 0
    for p_data in data.participants:
        p_id = p_data.get("id")
        if not p_id:
            continue
            
        try:
            from uuid import UUID as PyUUID
            p_uuid = PyUUID(str(p_id))
        except ValueError:
            continue
        
        result = await db.execute(
            select(Participant).where(
                Participant.id == p_uuid,
                Participant.event_id == event_id,
            )
        )
        participant = result.scalar_one_or_none()
        
        if participant:
            if "final_rank" in p_data:
                participant.final_rank = p_data["final_rank"]
            if "final_score" in p_data:
                participant.final_score = p_data["final_score"]
            updated += 1
    
    await db.flush()
    
    return BaseResponse(
        success=True,
        message=f"Updated ranks for {updated} participants.",
    )


@router.post("/events/{event_id}/generate-certificates", response_model=BaseResponse)
async def generate_certificates_for_event(
    event_id: UUID,
    regenerate: bool = False,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """
    Generate certificate records for all participants in an event.
    
    - Does NOT require the event to be finalized
    - If regenerate=True, recreates certificates for participants who already have one
    - Rank is optional - participants without rank still get certificates
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get default template
    result = await db.execute(
        select(CertificateTemplate).where(
            CertificateTemplate.event_id == event_id,
            CertificateTemplate.is_default == True,
        )
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=400, 
            detail="No default certificate template found. Create one and mark it as default.",
        )
    
    # Get all participants
    result = await db.execute(
        select(Participant).where(Participant.event_id == event_id)
    )
    participants = result.scalars().all()
    
    created = 0
    skipped = 0
    
    for participant in participants:
        # Check if certificate exists
        result = await db.execute(
            select(Certificate).where(Certificate.participant_id == participant.id)
        )
        existing = result.scalar_one_or_none()
        
        if existing and not regenerate:
            skipped += 1
            continue
        
        if existing and regenerate:
            # Delete old certificate
            await db.delete(existing)
        
        # Create new certificate
        cert = Certificate(
            participant_id=participant.id,
            template_id=template.id,
            display_name=participant.name or participant.username or participant.email.split("@")[0],
            team_name=None,
            rank=participant.final_rank,  # Can be None
            verification_code=secrets.token_urlsafe(16),
        )
        db.add(cert)
        created += 1
    
    await db.flush()
    
    # Queue background task to render certificates
    try:
        redis = await get_redis()
        await redis.enqueue_job(
            "bulk_generate_certificates_task",
            str(event_id),
            "png",
        )
    except Exception as e:
        # Don't fail if redis isn't available
        pass
    
    return BaseResponse(
        success=True,
        message=f"Created {created} certificates, skipped {skipped} existing. Rendering queued.",
    )


@router.post("/events/{event_id}/participants/import", response_model=ParticipantImportResponse)
async def import_participants(
    event_id: UUID,
    file: UploadFile = File(...),
    generate_passwords: bool = True,
    update_existing: bool = True,
    request: Request = None,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """
    Flexible participant import supporting multiple formats:
    - .txt: One email per line
    - .csv: Columns can include email, username, name, team_name, rank, score
    - .json: Array of participant objects
    
    Only email is required - all other fields are auto-generated if missing.
    
    Behavior:
    - New participants are added
    - Existing participants (by email) are updated with new data if update_existing=True
    - Field names are normalized (e.g., "E-mail", "email", "EMAIL" all work)
    - Extra columns in CSV are preserved in extra_data
    """
    import json as json_lib
    import re
    
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    content = await file.read()
    text = content.decode("utf-8").strip()
    filename = (file.filename or "").lower()
    
    # Parse file based on extension/content
    participants_data = []
    
    if filename.endswith(".txt") or (not filename.endswith((".csv", ".json")) and "\n" in text and "," not in text.split("\n")[0]):
        # Plain text file - one email per line
        email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        for line in text.split("\n"):
            line = line.strip()
            if line and email_regex.match(line):
                participants_data.append({"email": line})
                
    elif filename.endswith(".json") or text.startswith("["):
        # JSON file - array of objects
        try:
            data = json_lib.loads(text)
            if isinstance(data, list):
                participants_data = data
            else:
                raise HTTPException(status_code=400, detail="JSON must be an array of participants")
        except json_lib.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
            
    else:
        # CSV file - flexible column handling
        # Store ALL columns, with known fields mapped and extras preserved
        known_fields = {"email", "e-mail", "username", "name", "full_name", "fullname", 
                        "team_name", "team", "rank", "position", "score", "points"}
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            # Normalize column names (lowercase, strip)
            normalized = {k.lower().strip(): v.strip() for k, v in row.items() if v}
            if "email" in normalized or "e-mail" in normalized:
                email = normalized.get("email") or normalized.get("e-mail")
                # Collect extra fields not in known_fields
                extra_fields = {k: v for k, v in normalized.items() if k not in known_fields and v}
                participants_data.append({
                    "email": email,
                    "username": normalized.get("username"),
                    "name": normalized.get("name") or normalized.get("full_name") or normalized.get("fullname"),
                    "team_name": normalized.get("team_name") or normalized.get("team"),
                    "rank": normalized.get("rank") or normalized.get("position"),
                    "score": normalized.get("score") or normalized.get("points"),
                    "_extra": extra_fields,  # Store extra fields
                })
    
    if not participants_data:
        raise HTTPException(status_code=400, detail="No valid participants found in file")
    
    imported = 0
    updated = 0
    skipped = 0
    errors = []
    
    for i, p_data in enumerate(participants_data):
        email = (p_data.get("email") or "").strip().lower()
        
        if not email or "@" not in email:
            errors.append({"row": i + 1, "error": "Invalid or missing email"})
            continue
            
        try:
            # Check if exists
            result = await db.execute(
                select(Participant).where(
                    Participant.event_id == event_id,
                    Participant.email == email,
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                if update_existing:
                    # Update existing participant with new data
                    was_updated = False
                    
                    # Update name if provided
                    new_name = p_data.get("name")
                    if new_name and new_name != existing.name:
                        existing.name = new_name
                        was_updated = True
                    
                    # Update rank if provided
                    if p_data.get("rank"):
                        try:
                            new_rank = int(p_data["rank"])
                            if new_rank != existing.final_rank:
                                existing.final_rank = new_rank
                                was_updated = True
                        except (ValueError, TypeError):
                            pass
                    
                    # Update score if provided
                    if p_data.get("score"):
                        try:
                            new_score = float(p_data["score"])
                            if new_score != existing.final_score:
                                existing.final_score = new_score
                                was_updated = True
                        except (ValueError, TypeError):
                            pass
                    
                    # Update extra_data with new fields
                    extra_data = existing.extra_data or {}
                    if p_data.get("team_name"):
                        extra_data["team_name"] = p_data["team_name"]
                    if p_data.get("_extra"):
                        extra_data.update(p_data["_extra"])
                    if extra_data != existing.extra_data:
                        existing.extra_data = extra_data
                        was_updated = True
                    
                    if was_updated:
                        updated += 1
                    else:
                        skipped += 1
                else:
                    skipped += 1
                continue
            
            # Auto-generate username from email if not provided
            username = p_data.get("username")
            if not username:
                username = email.split("@")[0].lower()
                # Make unique if needed
                base_username = username
                counter = 1
                while True:
                    result = await db.execute(
                        select(Participant).where(
                            Participant.event_id == event_id,
                            Participant.username == username,
                        )
                    )
                    if not result.scalar_one_or_none():
                        break
                    username = f"{base_username}{counter}"
                    counter += 1
            
            password = secrets.token_urlsafe(12) if generate_passwords else "changeme123"
            
            # Parse rank/score if provided
            final_rank = None
            final_score = None
            if p_data.get("rank"):
                try:
                    final_rank = int(p_data["rank"])
                except (ValueError, TypeError):
                    pass
            if p_data.get("score"):
                try:
                    final_score = float(p_data["score"])
                except (ValueError, TypeError):
                    pass
            
            # Build extra_data from team_name and any extra CSV fields
            extra_data = {}
            if p_data.get("team_name"):
                extra_data["team_name"] = p_data["team_name"]
            if p_data.get("_extra"):
                extra_data.update(p_data["_extra"])
            
            participant = Participant(
                event_id=event_id,
                email=email,
                username=username.lower(),
                password_hash=hash_password(password),
                name=p_data.get("name") or email.split("@")[0],
                final_rank=final_rank,
                final_score=final_score,
                extra_data=extra_data,
                email_verified=True,
                email_verified_at=datetime.utcnow(),
                source="import",
            )
            
            db.add(participant)
            imported += 1
            
        except Exception as e:
            errors.append({
                "row": i + 1,
                "email": email,
                "error": str(e),
            })
    
    await db.flush()
    
    # Log import
    audit_log = AuditLog(
        action="admin.import_participants",
        user_id=user.id,
        actor_type="user",
        resource_type="event",
        resource_id=event_id,
        ip_address=get_client_ip(request),
        metadata={
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "errors": len(errors),
            "source_file": file.filename,
        },
    )
    db.add(audit_log)
    await db.flush()
    
    return ParticipantImportResponse(
        success=True,
        imported=imported,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )


@router.post("/events/{event_id}/participants/import-csv", response_model=ParticipantImportResponse)
async def import_participants_csv(
    event_id: UUID,
    file: UploadFile = File(...),
    generate_passwords: bool = True,
    request: Request = None,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """
    Import participants from CSV file.
    
    Expected columns: email, username, name (optional)
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Read CSV
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    
    imported = 0
    skipped = 0
    errors = []
    
    for i, row in enumerate(reader):
        email = row.get("email", "").strip().lower()
        username = row.get("username", "").strip().lower()
        name = row.get("name", "").strip()
        
        if not email or not username:
            errors.append({
                "row": i + 2,  # +2 for header and 0-indexing
                "error": "Missing email or username",
            })
            continue
        
        try:
            # Check if exists
            result = await db.execute(
                select(Participant).where(
                    Participant.event_id == event_id,
                    Participant.email == email,
                )
            )
            if result.scalar_one_or_none():
                skipped += 1
                continue
            
            password = secrets.token_urlsafe(12) if generate_passwords else "changeme123"
            
            participant = Participant(
                event_id=event_id,
                email=email,
                username=username,
                password_hash=hash_password(password),
                name=name or None,
                email_verified=True,
                email_verified_at=datetime.utcnow(),
                source="import",
            )
            
            db.add(participant)
            imported += 1
            
        except Exception as e:
            errors.append({
                "row": i + 2,
                "email": email,
                "error": str(e),
            })
    
    await db.flush()
    
    return ParticipantImportResponse(
        success=True,
        imported=imported,
        skipped=skipped,
        errors=errors,
    )


@router.post("/events/{event_id}/participants/{participant_id}/verify", response_model=BaseResponse)
async def verify_participant(
    event_id: UUID,
    participant_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Manually verify a participant's email."""
    result = await db.execute(
        select(Participant).where(
            Participant.id == participant_id,
            Participant.event_id == event_id,
        )
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    if participant.email_verified:
        return BaseResponse(success=True, message="Participant already verified")
    
    participant.email_verified = True
    participant.email_verified_at = func.now()
    await db.flush()
    
    return BaseResponse(success=True, message="Participant verified successfully")


@router.delete("/events/{event_id}/participants/{participant_id}", response_model=BaseResponse)
async def delete_participant(
    event_id: UUID,
    participant_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Delete a participant."""
    result = await db.execute(
        select(Participant).where(
            Participant.id == participant_id,
            Participant.event_id == event_id,
        )
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    await db.delete(participant)
    await db.flush()
    
    return BaseResponse(success=True, message="Participant deleted")


# =============================================================================
# Email Provider Management
# =============================================================================


@router.get("/providers", response_model=List[EmailProviderResponse])
async def list_providers(
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """List all email providers."""
    result = await db.execute(
        select(EmailProvider).order_by(EmailProvider.priority)
    )
    providers = result.scalars().all()
    
    responses = []
    for p in providers:
        # Get usage from Redis
        daily_used = await redis.get(f"ratelimit:{p.id}:daily")
        hourly_used = await redis.get(f"ratelimit:{p.id}:hourly")
        
        # Check availability
        circuit_key = f"circuit:{p.id}:open_until"
        circuit_open = await redis.get(circuit_key)
        available = p.is_active and not circuit_open
        
        responses.append(
            EmailProviderResponse(
                id=p.id,
                name=p.name,
                provider_type=p.provider_type.value,
                daily_limit=p.daily_limit,
                hourly_limit=p.hourly_limit,
                minute_limit=p.minute_limit,
                second_limit=p.second_limit,
                monthly_limit=p.monthly_limit,
                priority=p.priority,
                is_active=p.is_active,
                is_healthy=p.is_healthy,
                last_error=p.last_error,
                last_error_at=p.last_error_at,
                created_at=p.created_at,
                daily_used=int(daily_used) if daily_used else 0,
                hourly_used=int(hourly_used) if hourly_used else 0,
                available=available,
            )
        )
    
    return responses


@router.post("/providers", response_model=EmailProviderResponse)
async def create_provider(
    data: EmailProviderCreate,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Create a new email provider."""
    # Encrypt sensitive config fields
    config = dict(data.config)
    sensitive_fields = ["password", "api_key", "smtp_password"]
    for field in sensitive_fields:
        if field in config and config[field]:
            config[field] = encrypt_data(config[field])
    
    provider = EmailProvider(
        name=data.name,
        provider_type=ProviderType(data.provider_type),
        config=config,
        daily_limit=data.daily_limit,
        hourly_limit=data.hourly_limit,
        minute_limit=data.minute_limit,
        second_limit=data.second_limit,
        monthly_limit=data.monthly_limit,
        priority=data.priority,
    )
    
    db.add(provider)
    await db.flush()
    
    # Log
    audit_log = AuditLog(
        action="admin.provider_create",
        user_id=user.id,
        actor_type="user",
        resource_type="email_provider",
        resource_id=provider.id,
        ip_address=get_client_ip(request),
    )
    db.add(audit_log)
    await db.flush()
    
    return EmailProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type.value,
        daily_limit=provider.daily_limit,
        hourly_limit=provider.hourly_limit,
        minute_limit=provider.minute_limit,
        second_limit=provider.second_limit,
        monthly_limit=provider.monthly_limit,
        priority=provider.priority,
        is_active=provider.is_active,
        is_healthy=provider.is_healthy,
        last_error=provider.last_error,
        last_error_at=provider.last_error_at,
        created_at=provider.created_at,
    )


@router.patch("/providers/{provider_id}", response_model=EmailProviderResponse)
async def update_provider(
    provider_id: UUID,
    data: EmailProviderUpdate,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Update an email provider."""
    result = await db.execute(
        select(EmailProvider).where(EmailProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    if data.name is not None:
        provider.name = data.name
    if data.config is not None:
        # Encrypt sensitive fields
        config = dict(data.config)
        sensitive_fields = ["password", "api_key", "smtp_password"]
        for field in sensitive_fields:
            if field in config and config[field]:
                config[field] = encrypt_data(config[field])
        provider.config = config
    if data.daily_limit is not None:
        provider.daily_limit = data.daily_limit
    if data.hourly_limit is not None:
        provider.hourly_limit = data.hourly_limit
    if data.minute_limit is not None:
        provider.minute_limit = data.minute_limit
    if data.second_limit is not None:
        provider.second_limit = data.second_limit
    if data.monthly_limit is not None:
        provider.monthly_limit = data.monthly_limit
    if data.priority is not None:
        provider.priority = data.priority
    if data.is_active is not None:
        provider.is_active = data.is_active
    
    await db.flush()
    
    return EmailProviderResponse(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type.value,
        daily_limit=provider.daily_limit,
        hourly_limit=provider.hourly_limit,
        minute_limit=provider.minute_limit,
        second_limit=provider.second_limit,
        monthly_limit=provider.monthly_limit,
        priority=provider.priority,
        is_active=provider.is_active,
        is_healthy=provider.is_healthy,
        last_error=provider.last_error,
        last_error_at=provider.last_error_at,
        created_at=provider.created_at,
    )


@router.delete("/providers/{provider_id}", response_model=BaseResponse)
async def delete_provider(
    provider_id: UUID,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Delete an email provider."""
    result = await db.execute(
        select(EmailProvider).where(EmailProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    await db.delete(provider)
    await db.flush()
    
    return BaseResponse(success=True, message="Provider deleted")


@router.post("/providers/{provider_id}/test", response_model=EmailProviderTestResponse)
async def test_provider(
    provider_id: UUID,
    data: EmailProviderTestRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """Test an email provider by sending a test email."""
    result = await db.execute(
        select(EmailProvider).where(EmailProvider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    # Prepare provider config
    provider_config = {
        "id": provider.id,
        "name": provider.name,
        "type": provider.provider_type.value,
        "config": provider.config,
        "priority": 1,
        "daily_limit": 1000,  # Ignore limits for test
        "hourly_limit": 100,
        "minute_limit": 10,
        "second_limit": 1,
    }
    
    # Create test message
    message = EmailMessage(
        to=data.recipient_email,
        subject="ZeroPool Email Provider Test",
        body_html="""
        <html>
        <body>
        <h1>Test Email</h1>
        <p>This is a test email from ZeroPool to verify your email provider configuration.</p>
        <p>If you received this, your provider is working correctly!</p>
        <p><strong>Provider:</strong> {}</p>
        <p><strong>Timestamp:</strong> {}</p>
        </body>
        </html>
        """.format(provider.name, datetime.utcnow().isoformat()),
        body_text=f"ZeroPool Test Email\n\nProvider: {provider.name}\nTimestamp: {datetime.utcnow().isoformat()}",
    )
    
    # Send via orchestrator
    orchestrator = EmailOrchestrator(redis)
    result = await orchestrator.send(message, [provider_config], max_attempts=1)
    
    return EmailProviderTestResponse(
        success=result.success,
        sent=result.success,
        message_id=result.message_id,
        error=result.error,
    )


# =============================================================================
# Voucher Management
# =============================================================================


@router.get("/events/{event_id}/voucher-pools", response_model=List[VoucherPoolResponse])
async def list_voucher_pools(
    event_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """List voucher pools for an event."""
    result = await db.execute(
        select(VoucherPool)
        .where(VoucherPool.event_id == event_id)
        .order_by(VoucherPool.created_at.desc())
    )
    pools = result.scalars().all()
    
    return [
        VoucherPoolResponse(
            id=p.id,
            event_id=p.event_id,
            name=p.name,
            description=p.description,
            platform=p.platform,
            total_count=p.total_count,
            claimed_count=p.claimed_count,
            created_at=p.created_at,
        )
        for p in pools
    ]


@router.post("/events/{event_id}/voucher-pools", response_model=VoucherPoolResponse)
async def create_voucher_pool(
    event_id: UUID,
    data: VoucherPoolCreate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Create a new voucher pool."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Event not found")
    
    pool = VoucherPool(
        event_id=event_id,
        name=data.name,
        description=data.description,
        platform=data.platform,
    )
    
    db.add(pool)
    await db.flush()
    
    return VoucherPoolResponse(
        id=pool.id,
        event_id=pool.event_id,
        name=pool.name,
        description=pool.description,
        platform=pool.platform,
        total_count=pool.total_count,
        claimed_count=pool.claimed_count,
        created_at=pool.created_at,
    )


@router.post("/voucher-pools/{pool_id}/vouchers", response_model=BaseResponse)
async def upload_vouchers(
    pool_id: UUID,
    data: VoucherUploadRequest,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Upload voucher codes to a pool."""
    result = await db.execute(
        select(VoucherPool).where(VoucherPool.id == pool_id)
    )
    pool = result.scalar_one_or_none()
    
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    
    added = 0
    for code in data.codes:
        code = code.strip()
        if not code:
            continue
        
        # Check for duplicates
        result = await db.execute(
            select(Voucher).where(Voucher.code == code)
        )
        if result.scalar_one_or_none():
            continue
        
        voucher = Voucher(
            pool_id=pool_id,
            code=code,
        )
        db.add(voucher)
        added += 1
    
    pool.total_count += added
    await db.flush()
    
    return BaseResponse(success=True, message=f"Added {added} voucher codes")


@router.post("/voucher-pools/{pool_id}/vouchers/csv", response_model=BaseResponse)
async def upload_vouchers_csv(
    pool_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Upload voucher codes from CSV file."""
    result = await db.execute(
        select(VoucherPool).where(VoucherPool.id == pool_id)
    )
    pool = result.scalar_one_or_none()
    
    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")
    
    content = await file.read()
    text = content.decode("utf-8")
    
    added = 0
    for line in text.strip().split("\n"):
        code = line.strip()
        if not code or code.lower() == "code":  # Skip header
            continue
        
        # Check for duplicates
        result = await db.execute(
            select(Voucher).where(Voucher.code == code)
        )
        if result.scalar_one_or_none():
            continue
        
        voucher = Voucher(
            pool_id=pool_id,
            code=code,
        )
        db.add(voucher)
        added += 1
    
    pool.total_count += added
    await db.flush()
    
    return BaseResponse(success=True, message=f"Added {added} voucher codes")


# =============================================================================
# Export
# =============================================================================


@router.get("/events/{event_id}/export/participants")
async def export_participants(
    event_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Export participants as CSV."""
    result = await db.execute(
        select(Participant)
        .where(Participant.event_id == event_id)
        .order_by(Participant.final_rank.asc().nullslast())
    )
    participants = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "email", "username", "name", "verified", "rank", "score",
        "ctfd_provisioned", "source", "registered_at"
    ])
    
    for p in participants:
        writer.writerow([
            p.email,
            p.username,
            p.name or "",
            "yes" if p.email_verified else "no",
            p.final_rank or "",
            p.final_score or "",
            "yes" if p.ctfd_provisioned else "no",
            p.source,
            p.created_at.isoformat() if p.created_at else "",
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=participants-{event_id}.csv"
        },
    )


# =============================================================================
# Email Template Management
# =============================================================================


@router.get("/templates", response_model=List[EmailTemplateResponse])
async def list_templates(
    event_id: Optional[UUID] = None,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """List email templates (global or event-specific)."""
    query = select(EmailTemplate)
    
    if event_id:
        query = query.where(EmailTemplate.event_id == event_id)
    
    query = query.order_by(EmailTemplate.slug)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return [
        EmailTemplateResponse(
            id=t.id,
            event_id=t.event_id,
            slug=t.slug,
            name=t.name,
            description=t.description,
            subject=t.subject,
            body_html=t.body_html,
            body_text=t.body_text,
            variables=t.variables,
            is_active=t.is_active,
            created_at=t.created_at,
        )
        for t in templates
    ]


@router.post("/templates", response_model=EmailTemplateResponse)
async def create_template(
    data: EmailTemplateCreate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Create an email template."""
    template = EmailTemplate(
        event_id=data.event_id,
        slug=data.slug,
        name=data.name,
        description=data.description,
        subject=data.subject,
        body_html=data.body_html,
        body_text=data.body_text,
        variables=data.variables or [],
    )
    
    db.add(template)
    await db.flush()
    
    return EmailTemplateResponse(
        id=template.id,
        event_id=template.event_id,
        slug=template.slug,
        name=template.name,
        description=template.description,
        subject=template.subject,
        body_html=template.body_html,
        body_text=template.body_text,
        variables=template.variables,
        is_active=template.is_active,
        created_at=template.created_at,
    )


@router.get("/templates/{template_id}", response_model=EmailTemplateResponse)
async def get_template(
    template_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Get an email template."""
    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return EmailTemplateResponse(
        id=template.id,
        event_id=template.event_id,
        slug=template.slug,
        name=template.name,
        description=template.description,
        subject=template.subject,
        body_html=template.body_html,
        body_text=template.body_text,
        variables=template.variables,
        is_active=template.is_active,
        created_at=template.created_at,
    )


@router.patch("/templates/{template_id}", response_model=EmailTemplateResponse)
async def update_template(
    template_id: UUID,
    data: EmailTemplateUpdate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Update an email template."""
    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if data.name is not None:
        template.name = data.name
    if data.description is not None:
        template.description = data.description
    if data.subject is not None:
        template.subject = data.subject
    if data.body_html is not None:
        template.body_html = data.body_html
    if data.body_text is not None:
        template.body_text = data.body_text
    if data.variables is not None:
        template.variables = data.variables
    if data.is_active is not None:
        template.is_active = data.is_active
    
    template.updated_at = datetime.utcnow()
    await db.flush()
    
    return EmailTemplateResponse(
        id=template.id,
        event_id=template.event_id,
        slug=template.slug,
        name=template.name,
        description=template.description,
        subject=template.subject,
        body_html=template.body_html,
        body_text=template.body_text,
        variables=template.variables,
        is_active=template.is_active,
        created_at=template.created_at,
    )


@router.delete("/templates/{template_id}", response_model=BaseResponse)
async def delete_template(
    template_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Delete an email template."""
    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    await db.delete(template)
    await db.flush()
    
    return BaseResponse(success=True, message="Template deleted")


# =============================================================================
# Certificate Template Management
# =============================================================================


@router.get("/certificate-templates", response_model=List[CertificateTemplateResponse])
async def list_certificate_templates(
    event_id: Optional[UUID] = None,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """List certificate templates."""
    query = select(CertificateTemplate)
    
    if event_id:
        query = query.where(CertificateTemplate.event_id == event_id)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return [
        CertificateTemplateResponse(
            id=t.id,
            event_id=t.event_id,
            name=t.name,
            description=t.description,
            template_file=t.template_file,
            background_image=get_template_background_url(t.template_file),
            width=t.width,
            height=t.height,
            text_zones=t.text_zones,
            qr_zone=t.qr_zone,
            output_format=t.output_format,
            rank_from=t.rank_from,
            rank_to=t.rank_to,
            is_active=t.is_active,
            is_default=t.is_default,
            created_at=t.created_at,
        )
        for t in templates
    ]


@router.post("/certificate-templates", response_model=CertificateTemplateResponse)
async def create_certificate_template(
    data: CertificateTemplateCreate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Create a certificate template."""
    import base64
    from pathlib import Path
    
    template_file = ""
    
    # Handle background_image if provided
    if data.background_image:
        if data.background_image.startswith("data:"):
            # Base64 image - decode and save
            try:
                # Extract base64 data
                header, b64_data = data.background_image.split(",", 1)
                ext = "png"
                if "jpeg" in header or "jpg" in header:
                    ext = "jpg"
                elif "png" in header:
                    ext = "png"
                
                image_data = base64.b64decode(b64_data)
                
                # Save to uploads folder
                upload_dir = Path(settings.upload_dir) / "certificate-templates"
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                import uuid
                filename = f"{uuid.uuid4()}.{ext}"
                filepath = upload_dir / filename
                filepath.write_bytes(image_data)
                
                template_file = str(filepath)
            except Exception:
                pass  # Fall through to empty template_file
        elif data.background_image.startswith("/uploads/"):
            # URL path - convert to full file path
            relative_path = data.background_image[len("/uploads/"):]
            template_file = str(Path(settings.upload_dir) / relative_path)
        else:
            # Might be a full file path already
            template_file = data.background_image
    
    template = CertificateTemplate(
        event_id=data.event_id,
        name=data.name,
        description=data.description,
        template_file=template_file,
        width=data.width,
        height=data.height,
        text_zones=data.text_zones or [],
        qr_zone=data.qr_zone,
        output_format=data.output_format,
        rank_from=data.rank_from,
        rank_to=data.rank_to,
        is_default=data.is_default,
    )
    
    # If setting as default, unset other defaults for this event
    if data.is_default:
        result = await db.execute(
            select(CertificateTemplate).where(
                CertificateTemplate.event_id == data.event_id,
                CertificateTemplate.is_default == True,
            )
        )
        for existing in result.scalars().all():
            existing.is_default = False
    
    db.add(template)
    await db.flush()
    
    # Auto-generate certificates for all participants when template is marked as default
    if data.is_default:
        result = await db.execute(
            select(Participant).where(Participant.event_id == data.event_id)
        )
        participants = result.scalars().all()
        for participant in participants:
            # Check if participant already has a certificate
            cert_result = await db.execute(
                select(Certificate).where(Certificate.participant_id == participant.id)
            )
            existing_cert = cert_result.scalar_one_or_none()
            if not existing_cert:
                cert = Certificate(
                    participant_id=participant.id,
                    template_id=template.id,
                    display_name=participant.name or participant.username or participant.email.split("@")[0],
                    rank=participant.final_rank,
                    verification_code=secrets.token_urlsafe(16),
                )
                db.add(cert)
        await db.flush()
    
    return CertificateTemplateResponse(
        id=template.id,
        event_id=template.event_id,
        name=template.name,
        description=template.description,
        template_file=template.template_file,
        background_image=get_template_background_url(template.template_file),
        width=template.width,
        height=template.height,
        text_zones=template.text_zones,
        qr_zone=template.qr_zone,
        output_format=template.output_format,
        rank_from=template.rank_from,
        rank_to=template.rank_to,
        is_active=template.is_active,
        is_default=template.is_default,
        created_at=template.created_at,
    )


@router.get("/certificate-templates/{template_id}", response_model=CertificateTemplateResponse)
async def get_certificate_template(
    template_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Get a single certificate template by ID."""
    result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return CertificateTemplateResponse(
        id=template.id,
        event_id=template.event_id,
        name=template.name,
        description=template.description,
        template_file=template.template_file,
        background_image=get_template_background_url(template.template_file),
        width=template.width,
        height=template.height,
        text_zones=template.text_zones or [],
        qr_zone=template.qr_zone,
        output_format=template.output_format,
        rank_from=template.rank_from,
        rank_to=template.rank_to,
        is_active=template.is_active,
        is_default=template.is_default,
        created_at=template.created_at,
    )


@router.post("/certificate-templates/{template_id}/upload", response_model=CertificateTemplateResponse)
async def upload_certificate_template_image(
    template_id: UUID,
    file: UploadFile = File(...),
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Upload template background image."""
    result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400, detail="File must be an image"
        )
    
    # Save file
    upload_dir = Path(settings.upload_dir) / "certificate-templates"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    ext = file.filename.split(".")[-1] if "." in file.filename else "png"
    filename = f"{template_id}.{ext}"
    filepath = upload_dir / filename
    
    content = await file.read()
    filepath.write_bytes(content)
    
    # Update template
    template.template_file = str(filepath)
    await db.flush()
    
    # Return updated template with background_image URL
    return CertificateTemplateResponse(
        id=template.id,
        event_id=template.event_id,
        name=template.name,
        description=template.description,
        template_file=template.template_file,
        background_image=get_template_background_url(template.template_file),
        width=template.width,
        height=template.height,
        text_zones=template.text_zones or [],
        qr_zone=template.qr_zone,
        output_format=template.output_format,
        rank_from=template.rank_from,
        rank_to=template.rank_to,
        is_active=template.is_active,
        is_default=template.is_default,
        created_at=template.created_at,
    )


@router.patch("/certificate-templates/{template_id}", response_model=CertificateTemplateResponse)
async def update_certificate_template(
    template_id: UUID,
    data: CertificateTemplateUpdate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Update a certificate template."""
    result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if data.name is not None:
        template.name = data.name
    if data.description is not None:
        template.description = data.description
    if data.width is not None:
        template.width = data.width
    if data.height is not None:
        template.height = data.height
    if data.text_zones is not None:
        template.text_zones = data.text_zones
    if data.qr_zone is not None:
        template.qr_zone = data.qr_zone
    if data.output_format is not None:
        template.output_format = data.output_format
    if data.rank_from is not None:
        template.rank_from = data.rank_from
    if data.rank_to is not None:
        template.rank_to = data.rank_to
    if data.is_active is not None:
        template.is_active = data.is_active
    if data.is_default is not None:
        if data.is_default:
            # Unset other defaults
            result = await db.execute(
                select(CertificateTemplate).where(
                    CertificateTemplate.event_id == template.event_id,
                    CertificateTemplate.id != template_id,
                    CertificateTemplate.is_default == True,
                )
            )
            for existing in result.scalars().all():
                existing.is_default = False
        template.is_default = data.is_default
        
        # AUTO-GENERATE certificates when template is marked as default
        if data.is_default:
            result = await db.execute(
                select(Participant).where(Participant.event_id == template.event_id)
            )
            participants = result.scalars().all()
            
            for participant in participants:
                # Check if certificate already exists
                cert_result = await db.execute(
                    select(Certificate).where(Certificate.participant_id == participant.id)
                )
                if not cert_result.scalar_one_or_none():
                    cert = Certificate(
                        participant_id=participant.id,
                        template_id=template.id,
                        display_name=participant.name or participant.username or participant.email.split("@")[0],
                        team_name=None,
                        rank=participant.final_rank,
                        verification_code=secrets.token_urlsafe(16),
                    )
                    db.add(cert)
    
    # Handle background_image update
    if data.background_image is not None:
        import base64
        from pathlib import Path
        
        if data.background_image.startswith("data:"):
            # Base64 image - decode and save
            try:
                header, b64_data = data.background_image.split(",", 1)
                ext = "png"
                if "jpeg" in header or "jpg" in header:
                    ext = "jpg"
                
                image_data = base64.b64decode(b64_data)
                
                upload_dir = Path(settings.upload_dir) / "certificate-templates"
                upload_dir.mkdir(parents=True, exist_ok=True)
                
                filename = f"{template_id}.{ext}"
                filepath = upload_dir / filename
                filepath.write_bytes(image_data)
                
                template.template_file = str(filepath)
            except Exception:
                pass
        elif data.background_image.startswith("/uploads/"):
            relative_path = data.background_image[len("/uploads/"):]
            template.template_file = str(Path(settings.upload_dir) / relative_path)
        elif data.background_image:
            template.template_file = data.background_image
    
    await db.flush()
    
    return CertificateTemplateResponse(
        id=template.id,
        event_id=template.event_id,
        name=template.name,
        description=template.description,
        template_file=template.template_file,
        background_image=get_template_background_url(template.template_file),
        width=template.width,
        height=template.height,
        text_zones=template.text_zones,
        qr_zone=template.qr_zone,
        output_format=template.output_format,
        rank_from=template.rank_from,
        rank_to=template.rank_to,
        is_active=template.is_active,
        is_default=template.is_default,
        created_at=template.created_at,
    )


@router.delete("/certificate-templates/{template_id}", response_model=BaseResponse)
async def delete_certificate_template(
    template_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Delete a certificate template."""
    result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Delete the template file if it exists
    if template.template_file:
        try:
            filepath = Path(template.template_file)
            if filepath.exists():
                filepath.unlink()
        except Exception:
            pass  # Ignore file deletion errors
    
    await db.delete(template)
    await db.flush()
    
    return BaseResponse(success=True, message="Template deleted successfully")


# =============================================================================
# Prize Rules Management
# =============================================================================


@router.get("/events/{event_id}/prize-rules", response_model=List[PrizeRuleResponse])
async def list_prize_rules(
    event_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """List prize rules for an event."""
    result = await db.execute(
        select(PrizeRule)
        .where(PrizeRule.event_id == event_id)
        .order_by(PrizeRule.rank_min)
    )
    rules = result.scalars().all()
    
    responses = []
    for r in rules:
        # Get pool name if applicable
        pool_name = None
        if r.voucher_pool_id:
            pool_result = await db.execute(
                select(VoucherPool.name).where(VoucherPool.id == r.voucher_pool_id)
            )
            pool_name = pool_result.scalar()
        
        responses.append(
            PrizeRuleResponse(
                id=r.id,
                event_id=r.event_id,
                name=r.name,
                description=r.description,
                rank_min=r.rank_min,
                rank_max=r.rank_max,
                prize_type=r.prize_type,
                prize_value=r.prize_value,
                voucher_pool_id=r.voucher_pool_id,
                voucher_pool_name=pool_name,
                is_active=r.is_active,
                created_at=r.created_at,
            )
        )
    
    return responses


@router.post("/events/{event_id}/prize-rules", response_model=PrizeRuleResponse)
async def create_prize_rule(
    event_id: UUID,
    data: PrizeRuleCreate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Create a prize rule."""
    result = await db.execute(select(Event).where(Event.id == event_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Validate voucher pool if specified
    pool_name = None
    if data.voucher_pool_id:
        result = await db.execute(
            select(VoucherPool).where(VoucherPool.id == data.voucher_pool_id)
        )
        pool = result.scalar_one_or_none()
        if not pool:
            raise HTTPException(status_code=404, detail="Voucher pool not found")
        pool_name = pool.name
    
    rule = PrizeRule(
        event_id=event_id,
        name=data.name,
        description=data.description,
        rank_min=data.rank_min,
        rank_max=data.rank_max,
        prize_type=data.prize_type,
        prize_value=data.prize_value,
        voucher_pool_id=data.voucher_pool_id,
    )
    
    db.add(rule)
    await db.flush()
    
    return PrizeRuleResponse(
        id=rule.id,
        event_id=rule.event_id,
        name=rule.name,
        description=rule.description,
        rank_min=rule.rank_min,
        rank_max=rule.rank_max,
        prize_type=rule.prize_type,
        prize_value=rule.prize_value,
        voucher_pool_id=rule.voucher_pool_id,
        voucher_pool_name=pool_name,
        is_active=rule.is_active,
        created_at=rule.created_at,
    )


@router.delete("/prize-rules/{rule_id}", response_model=BaseResponse)
async def delete_prize_rule(
    rule_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Delete a prize rule."""
    result = await db.execute(
        select(PrizeRule).where(PrizeRule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    await db.delete(rule)
    await db.flush()
    
    return BaseResponse(success=True, message="Prize rule deleted")


# =============================================================================
# Campaign Management
# =============================================================================


@router.get("/campaigns", response_model=List[CampaignResponse])
async def list_campaigns(
    event_id: Optional[UUID] = None,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """List email campaigns."""
    query = select(EmailCampaign)
    
    if event_id:
        query = query.where(EmailCampaign.event_id == event_id)
    
    query = query.order_by(EmailCampaign.created_at.desc())
    
    result = await db.execute(query)
    campaigns = result.scalars().all()
    
    return [
        CampaignResponse(
            id=c.id,
            event_id=c.event_id,
            template_id=c.template_id,
            name=c.name,
            status=c.status.value,
            filter_criteria=c.filter_criteria,
            total_recipients=c.total_recipients,
            sent_count=c.sent_count,
            failed_count=c.failed_count,
            scheduled_at=c.scheduled_at,
            started_at=c.started_at,
            completed_at=c.completed_at,
            created_at=c.created_at,
        )
        for c in campaigns
    ]


@router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(
    data: CampaignCreate,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Create an email campaign."""
    # Validate event
    if data.event_id:
        result = await db.execute(
            select(Event).where(Event.id == data.event_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Event not found")
    
    # Validate template
    result = await db.execute(
        select(EmailTemplate).where(EmailTemplate.id == data.template_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Template not found")
    
    campaign = EmailCampaign(
        event_id=data.event_id,
        template_id=data.template_id,
        name=data.name,
        filter_criteria=data.filter_criteria or {},
        scheduled_at=data.scheduled_at,
    )
    
    db.add(campaign)
    await db.flush()
    
    return CampaignResponse(
        id=campaign.id,
        event_id=campaign.event_id,
        template_id=campaign.template_id,
        name=campaign.name,
        status=campaign.status.value,
        filter_criteria=campaign.filter_criteria,
        total_recipients=campaign.total_recipients,
        sent_count=campaign.sent_count,
        failed_count=campaign.failed_count,
        scheduled_at=campaign.scheduled_at,
        started_at=campaign.started_at,
        completed_at=campaign.completed_at,
        created_at=campaign.created_at,
    )


@router.post("/campaigns/{campaign_id}/start", response_model=BaseResponse)
async def start_campaign(
    campaign_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """
    Start a campaign.
    
    This sets the campaign to pending and the worker will pick it up.
    """
    result = await db.execute(
        select(EmailCampaign).where(EmailCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status != EmailStatus.DRAFT:
        raise HTTPException(
            status_code=400,
            detail=f"Campaign is already {campaign.status.value}",
        )
    
    # Count recipients
    query = select(func.count()).select_from(Participant)
    
    if campaign.event_id:
        query = query.where(Participant.event_id == campaign.event_id)
    
    criteria = campaign.filter_criteria
    if criteria.get("verified_only"):
        query = query.where(Participant.email_verified == True)
    if criteria.get("unverified_only"):
        query = query.where(Participant.email_verified == False)
    
    total = await db.scalar(query) or 0
    
    campaign.total_recipients = total
    campaign.status = EmailStatus.PENDING
    campaign.started_at = datetime.utcnow()
    
    await db.flush()
    
    return BaseResponse(
        success=True,
        message=f"Campaign started with {total} recipients",
    )


@router.post("/campaigns/{campaign_id}/cancel", response_model=BaseResponse)
async def cancel_campaign(
    campaign_id: UUID,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """Cancel a running campaign."""
    result = await db.execute(
        select(EmailCampaign).where(EmailCampaign.id == campaign_id)
    )
    campaign = result.scalar_one_or_none()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status not in [EmailStatus.PENDING, EmailStatus.PROCESSING]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel campaign with status {campaign.status.value}",
        )
    
    campaign.status = EmailStatus.FAILED
    campaign.completed_at = datetime.utcnow()
    
    await db.flush()
    
    return BaseResponse(success=True, message="Campaign cancelled")


# =============================================================================
# Event Finalization
# =============================================================================


@router.post("/events/{event_id}/finalize", response_model=BaseResponse)
async def finalize_event(
    event_id: UUID,
    request: Request,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """
    Finalize an event.
    
    This:
    1. Sets event status to COMPLETED
    2. Assigns prizes based on prize rules
    3. Creates certificate records
    """
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get prize rules
    result = await db.execute(
        select(PrizeRule)
        .where(PrizeRule.event_id == event_id, PrizeRule.is_active == True)
        .order_by(PrizeRule.rank_min)
    )
    rules = result.scalars().all()
    
    # Get participants with rankings (for prizes)
    result = await db.execute(
        select(Participant)
        .where(
            Participant.event_id == event_id,
            Participant.final_rank.isnot(None),
        )
        .order_by(Participant.final_rank)
    )
    ranked_participants = result.scalars().all()
    
    # Get ALL participants (for certificates - rank is optional)
    result = await db.execute(
        select(Participant)
        .where(Participant.event_id == event_id)
    )
    all_participants = result.scalars().all()
    
    prizes_assigned = 0
    certs_created = 0
    
    # Assign prizes only to ranked participants
    for participant in ranked_participants:
        rank = participant.final_rank
        
        # Find matching prize rules
        for rule in rules:
            if rule.rank_min <= rank <= (rule.rank_max or rank):
                # Check if prize already assigned
                result = await db.execute(
                    select(Prize).where(
                        Prize.participant_id == participant.id,
                        Prize.prize_rule_id == rule.id,
                    )
                )
                if result.scalar_one_or_none():
                    continue
                
                # Get voucher if needed
                voucher_id = None
                if rule.voucher_pool_id:
                    result = await db.execute(
                        select(Voucher).where(
                            Voucher.pool_id == rule.voucher_pool_id,
                            Voucher.status == VoucherStatus.AVAILABLE,
                        ).limit(1)
                    )
                    voucher = result.scalar_one_or_none()
                    if voucher:
                        voucher.status = VoucherStatus.RESERVED
                        voucher_id = voucher.id
                
                # Create prize
                prize = Prize(
                    participant_id=participant.id,
                    prize_rule_id=rule.id,
                    voucher_id=voucher_id,
                    prize_type=rule.prize_type,
                    prize_value=rule.prize_value,
                )
                db.add(prize)
                prizes_assigned += 1
    
    # Get default template once for certificate creation
    result = await db.execute(
        select(CertificateTemplate).where(
            CertificateTemplate.event_id == event_id,
            CertificateTemplate.is_default == True,
        )
    )
    default_template = result.scalar_one_or_none()
    
    # Create certificates for ALL participants (rank is optional)
    for participant in all_participants:
        # Check if certificate already exists
        result = await db.execute(
            select(Certificate).where(Certificate.participant_id == participant.id)
        )
        if not result.scalar_one_or_none() and default_template:
            cert = Certificate(
                participant_id=participant.id,
                template_id=default_template.id,
                display_name=participant.name or participant.username or participant.email.split("@")[0],
                team_name=None,  # Will be populated if team mode
                rank=participant.final_rank,  # Can be None
                verification_code=secrets.token_urlsafe(16),
            )
            db.add(cert)
            certs_created += 1
    
    event.status = EventStatus.COMPLETED
    
    # Audit log
    audit_log = AuditLog(
        action="admin.event_finalize",
        user_id=user.id,
        actor_type="user",
        resource_type="event",
        resource_id=event_id,
        ip_address=get_client_ip(request),
        metadata={
            "prizes_assigned": prizes_assigned,
            "certificates_created": certs_created,
        },
    )
    db.add(audit_log)
    
    await db.flush()
    
    return BaseResponse(
        success=True,
        message=f"Event finalized. Assigned {prizes_assigned} prizes, created {certs_created} certificates.",
    )


# =============================================================================
# CTFd Integration
# =============================================================================


@router.post("/events/{event_id}/ctfd/sync", response_model=BaseResponse)
async def sync_ctfd(
    event_id: UUID,
    request: Request,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """
    Trigger CTFd synchronization.
    
    This fetches the scoreboard from CTFd and updates participant rankings
    in the ZeroPool database. Participants are matched by:
    1. ctfd_user_id (if they were provisioned to CTFd)
    2. name match (for imported participants)
    3. team name match (for team mode)
    """
    from app.services.ctfd import CTFdSyncService
    
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if not event.ctfd_url or not event.ctfd_api_key:
        raise HTTPException(
            status_code=400,
            detail="CTFd URL and API key are required",
        )
    
    # Decrypt API key
    from app.utils.security import decrypt_data
    api_key = decrypt_data(event.ctfd_api_key)
    
    # Create sync service with database access
    sync_service = CTFdSyncService(event.ctfd_url, api_key, db=db)
    
    try:
        results = await sync_service.sync_results_for_event(event_id)
        
        # Update sync timestamp
        event.ctfd_synced_at = datetime.utcnow()
        
        # Audit log
        audit_log = AuditLog(
            action="admin.ctfd_sync",
            user_id=user.id,
            actor_type="user",
            resource_type="event",
            resource_id=event_id,
            ip_address=get_client_ip(request),
            metadata={"rankings_updated": len(results)},
        )
        db.add(audit_log)
        
        await db.flush()
        
        return BaseResponse(
            success=True,
            message=f"Synced {len(results)} participant rankings from CTFd",
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/events/{event_id}/ctfd/provision", response_model=BaseResponse)
async def provision_ctfd_users(
    event_id: UUID,
    request: Request,
    user: User = Depends(require_organizer),
    db: AsyncSession = Depends(get_session),
):
    """
    Provision verified participants to CTFd.
    
    Creates user accounts on the linked CTFd instance.
    """
    from app.services.ctfd import CTFdSyncService
    
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    if not event.ctfd_url or not event.ctfd_api_key:
        raise HTTPException(
            status_code=400,
            detail="CTFd URL and API key are required",
        )
    
    from app.utils.security import decrypt_data
    api_key = decrypt_data(event.ctfd_api_key)
    
    # Create sync service with corrected initialization
    sync_service = CTFdSyncService(event.ctfd_url, api_key, db=db)
    
    try:
        provisioned = await sync_service.provision_users_for_event(event_id)
        
        # Audit log
        audit_log = AuditLog(
            action="admin.ctfd_provision",
            user_id=user.id,
            actor_type="user",
            resource_type="event",
            resource_id=event_id,
            ip_address=get_client_ip(request),
            metadata={"provisioned": provisioned},
        )
        db.add(audit_log)
        
        await db.flush()
        
        return BaseResponse(
            success=True,
            message=f"Provisioned {provisioned} users to CTFd",
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# User Management (Admin only)
# =============================================================================


@router.get("/users")
async def list_users(
    page: int = 1,
    per_page: int = 50,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """List admin/organizer users."""
    query = select(User).order_by(User.created_at.desc())
    
    count_query = select(func.count()).select_from(User)
    total = await db.scalar(count_query) or 0
    
    query = query.offset((page - 1) * per_page).limit(per_page)
    
    result = await db.execute(query)
    users = result.scalars().all()
    
    return {
        "success": True,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page if per_page > 0 else 0,
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "username": u.username,
                "name": u.name,
                "role": u.role.value,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ],
    }


@router.patch("/users/{user_id}/role", response_model=BaseResponse)
async def update_user_role(
    user_id: UUID,
    role: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_session),
):
    """Update a user's role."""
    from app.models import UserRole
    
    result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
    
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        target_user.role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    await db.flush()
    
    return BaseResponse(success=True, message=f"User role updated to {role}")
