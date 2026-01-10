"""
Participant API Routes

Endpoints for authenticated participants.
"""

from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    create_session,
    delete_session,
    get_client_ip,
    get_current_session,
    get_redis,
    get_user_agent,
    require_participant,
    require_verified_participant,
)
from app.config import get_settings
from app.database import get_session
from app.models import AuditLog, Certificate, EmailLog, EmailStatus, Event, Participant, Prize, Session, Team, TeamMember
from app.schemas import BaseResponse, CertificateCustomizeRequest, ParticipantResponse, ParticipantUpdate
from app.services.email import EmailMessage, EmailOrchestrator, render_email, render_subject

router = APIRouter()
settings = get_settings()


# =============================================================================
# Magic Link Login (Passwordless)
# =============================================================================


class RequestAccessRequest(BaseModel):
    """Request magic link access."""
    email: EmailStr


@router.post("/request-access", response_model=BaseResponse)
async def request_access(
    request: Request,
    data: RequestAccessRequest,
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """
    Request a magic link to access the participant portal.
    
    This sends an email with a one-time login link.
    If the email is registered for multiple events, separate magic links
    are sent for each event (per-event sessions for security isolation).
    """
    # Find ALL participants by email (could be in multiple events)
    result = await db.execute(
        select(Participant).where(
            Participant.email == data.email.lower(),
            Participant.email_verified == True,
            Participant.is_blocked == False,
        )
    )
    participants = result.scalars().all()
    
    # Always return success to prevent email enumeration
    if not participants:
        return BaseResponse(
            success=True,
            message="If your email is registered, you will receive an access link shortly.",
        )
    
    now = datetime.now(timezone.utc)
    sent_count = 0
    
    # Process each participant (one per event) independently
    for participant in participants:
        # Rate limit: max 1 request per 5 minutes per event
        if participant.magic_link_sent_at:
            sent_at = participant.magic_link_sent_at
            # Handle timezone-naive datetime
            if sent_at.tzinfo is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            time_since_last = now - sent_at
            if time_since_last < timedelta(minutes=5):
                # Skip this event, but continue with others
                continue
        
        # Generate magic link token for this event's participant
        magic_token = secrets.token_urlsafe(32)
        participant.magic_link_token = magic_token
        participant.magic_link_sent_at = now
        participant.magic_link_expires_at = now + timedelta(hours=1)
        
        await db.flush()
        
        # Get event for email context
        event_result = await db.execute(
            select(Event).where(Event.id == participant.event_id)
        )
        event = event_result.scalar_one_or_none()
        
        # Build magic link URL
        magic_link_url = f"{settings.app_url}/portal/verify?token={magic_token}"
        
        # Send email for this event
        await _send_magic_link_email(db, redis, participant, event, magic_link_url)
        sent_count += 1
    
    return BaseResponse(
        success=True,
        message="If your email is registered, you will receive an access link shortly.",
    )


@router.post("/verify-magic-link", response_model=BaseResponse)
async def verify_magic_link(
    request: Request,
    response: Response,
    token: str,
    db: AsyncSession = Depends(get_session),
):
    """
    Verify magic link token and create session.
    """
    result = await db.execute(
        select(Participant).where(
            Participant.magic_link_token == token,
            Participant.magic_link_expires_at > datetime.now(timezone.utc),
            Participant.is_blocked == False,
        )
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired access link. Please request a new one.",
        )
    
    # Clear magic link token
    participant.magic_link_token = None
    participant.magic_link_expires_at = None
    
    # Create session
    session_id = await create_session(
        db,
        participant_id=participant.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    # Log access
    audit_log = AuditLog(
        action="participant.magic_link_login",
        participant_id=participant.id,
        actor_type="participant",
        ip_address=get_client_ip(request),
    )
    db.add(audit_log)
    await db.flush()
    
    # Set session cookie
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=settings.session_cookie_httponly,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_lifetime_hours * 3600,
    )
    
    return BaseResponse(
        success=True,
        message="Login successful",
    )


@router.post("/logout", response_model=BaseResponse)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_session),
    session=Depends(get_current_session),
):
    """
    Logout participant and clear session.
    """
    if session:
        await delete_session(db, session.id)
    
    response.delete_cookie(settings.session_cookie_name)
    
    return BaseResponse(success=True, message="Logged out successfully")


async def _send_magic_link_email(
    db: AsyncSession,
    redis,
    participant: Participant,
    event: Event,
    magic_link_url: str,
):
    """Send magic link access email."""
    from app.models import EmailProvider
    
    # Get active providers
    result = await db.execute(
        select(EmailProvider).where(
            EmailProvider.is_active == True
        ).order_by(EmailProvider.priority)
    )
    providers = result.scalars().all()
    
    if not providers:
        print("Warning: No email providers configured")
        return
    
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
    
    event_name = event.name if event else "ZeroPool Event"
    
    body_html = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px;">
        <h2>Access Your Portal</h2>
        <p>Hi {participant.name or participant.username},</p>
        <p>Click the link below to access your participant portal for {event_name}:</p>
        <p><a href="{magic_link_url}" style="background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">Access Portal</a></p>
        <p style="color: #666; font-size: 14px;">This link expires in 1 hour.</p>
        <p style="color: #666; font-size: 14px;">If you didn't request this, you can safely ignore this email.</p>
    </body>
    </html>
    """
    
    body_text = f"""
    Access Your Portal
    
    Hi {participant.name or participant.username},
    
    Click the link below to access your participant portal for {event_name}:
    
    {magic_link_url}
    
    This link expires in 1 hour.
    
    If you didn't request this, you can safely ignore this email.
    """
    
    message = EmailMessage(
        to=participant.email,
        subject=f"Access Your {event_name} Portal",
        body_html=body_html,
        body_text=body_text,
        participant_id=participant.id,
        template_slug="magic_link",
    )
    
    orchestrator = EmailOrchestrator(redis)
    result = await orchestrator.send(message, provider_configs)
    
    email_log = EmailLog(
        recipient_email=participant.email,
        participant_id=participant.id,
        provider_id=result.provider_id,
        provider_name=result.provider_name,
        subject=message.subject,
        template_slug="magic_link",
        status=EmailStatus.SENT if result.success else EmailStatus.FAILED,
        error_message=result.error,
        attempts=result.attempts,
        sent_at=datetime.utcnow() if result.success else None,
    )
    db.add(email_log)
    await db.flush()


# =============================================================================
# Profile Endpoints
# =============================================================================


@router.get("/me", response_model=ParticipantResponse)
async def get_current_participant_info(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_session),
):
    """Get current participant's profile."""
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
        metadata=participant.metadata,
    )


@router.patch("/me", response_model=ParticipantResponse)
async def update_current_participant(
    data: ParticipantUpdate,
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_session),
):
    """Update current participant's profile."""
    if data.name is not None:
        participant.name = data.name
    
    if data.metadata is not None:
        participant.metadata = {**participant.metadata, **data.metadata}
    
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
        metadata=participant.metadata,
    )


@router.get("/me/event")
async def get_participant_event(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_session),
):
    """Get the event the participant is registered for."""
    result = await db.execute(
        select(Event).where(Event.id == participant.event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    return {
        "id": str(event.id),
        "name": event.name,
        "slug": event.slug,
        "status": event.status.value,
        "ctfd_url": event.ctfd_url,
        "event_start": event.event_start.isoformat() if event.event_start else None,
        "event_end": event.event_end.isoformat() if event.event_end else None,
    }


@router.get("/me/events")
async def get_participant_events(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_session),
):
    """
    Get all events the participant is registered for.
    
    Returns a list of events.
    """
    # Get the event(s) the participant is part of
    result = await db.execute(
        select(Event).where(Event.id == participant.event_id)
    )
    events = result.scalars().all()
    
    return [
        {
            "id": str(event.id),
            "name": event.name,
            "slug": event.slug,
            "status": event.status.value,
            "description": event.description,
            "start_date": event.event_start.isoformat() if event.event_start else None,
            "end_date": event.event_end.isoformat() if event.event_end else None,
            "ctfd_url": event.ctfd_url,
        }
        for event in events
    ]


@router.get("/me/team")
async def get_participant_team(
    participant: Participant = Depends(require_participant),
    db: AsyncSession = Depends(get_session),
):
    """Get the participant's team (if any)."""
    # Find team membership
    result = await db.execute(
        select(TeamMember).where(TeamMember.participant_id == participant.id)
    )
    membership = result.scalar_one_or_none()
    
    if not membership:
        return {"team": None}
    
    # Get team details
    result = await db.execute(
        select(Team).where(Team.id == membership.team_id)
    )
    team = result.scalar_one_or_none()
    
    if not team:
        return {"team": None}
    
    # Get team members
    result = await db.execute(
        select(TeamMember, Participant)
        .join(Participant, TeamMember.participant_id == Participant.id)
        .where(TeamMember.team_id == team.id)
    )
    members_data = result.all()
    
    members = [
        {
            "id": str(p.id),
            "username": p.username,
            "name": p.name,
            "is_captain": tm.is_captain,
        }
        for tm, p in members_data
    ]
    
    return {
        "team": {
            "id": str(team.id),
            "name": team.name,
            "final_rank": team.final_rank,
            "final_score": team.final_score,
            "members": members,
        }
    }


@router.get("/me/results")
async def get_participant_results(
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """
    Get participant's final results.
    
    Available after event ends and results are synced.
    """
    # Check if event has ended
    result = await db.execute(
        select(Event).where(Event.id == participant.event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    if event.status.value not in ["ended", "archived"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Results not yet available",
        )
    
    # Get prizes
    result = await db.execute(
        select(Prize).where(Prize.participant_id == participant.id)
    )
    prizes = result.scalars().all()
    
    return {
        "rank": participant.final_rank,
        "score": participant.final_score,
        "prizes": [
            {
                "id": str(p.id),
                "type": p.prize_type,
                "status": p.status.value,
                "claimed_at": p.claimed_at.isoformat() if p.claimed_at else None,
            }
            for p in prizes
        ],
    }


@router.get("/me/prizes")
async def get_participant_prizes(
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """
    Get participant's prizes.
    
    Returns list of prizes assigned to this participant.
    """
    result = await db.execute(
        select(Prize).where(Prize.participant_id == participant.id)
    )
    prizes = result.scalars().all()
    
    return [
        {
            "id": str(p.id),
            "type": p.prize_type,
            "status": p.status.value if hasattr(p.status, 'value') else p.status,
            "claimed_at": p.claimed_at.isoformat() if p.claimed_at else None,
        }
        for p in prizes
    ]


@router.get("/me/certificates")
async def get_participant_certificates(
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """
    Get participant's certificates.
    
    Returns list of certificates generated for this participant.
    Uses lazy creation - if no certificate exists but participant is eligible,
    creates one on-the-fly using the default template.
    """
    from app.models import CertificateTemplate
    import secrets
    
    result = await db.execute(
        select(Certificate).where(Certificate.participant_id == participant.id)
    )
    certificates = list(result.scalars().all())
    
    # Get event info
    event_result = await db.execute(
        select(Event).where(Event.id == participant.event_id)
    )
    event = event_result.scalar_one_or_none()
    event_name = event.name if event else "Unknown Event"
    
    # LAZY CREATION: If no certificates exist for a verified participant, create one
    if not certificates and participant.email_verified:
        # Find a default template for this event (or global default)
        template_result = await db.execute(
            select(CertificateTemplate).where(
                CertificateTemplate.event_id == participant.event_id,
                CertificateTemplate.is_default == True,
            )
        )
        template = template_result.scalar_one_or_none()
        
        # If no event-specific default, try global default
        if not template:
            template_result = await db.execute(
                select(CertificateTemplate).where(
                    CertificateTemplate.event_id.is_(None),
                    CertificateTemplate.is_default == True,
                )
            )
            template = template_result.scalar_one_or_none()
        
        # If still no template, try any template for the event
        if not template:
            template_result = await db.execute(
                select(CertificateTemplate).where(
                    CertificateTemplate.event_id == participant.event_id,
                ).limit(1)
            )
            template = template_result.scalar_one_or_none()
        
        if template:
            # Create certificate record (lazy - will be generated on download)
            new_cert = Certificate(
                participant_id=participant.id,
                template_id=template.id,
                display_name=participant.name or participant.username,
                team_name=participant.extra_data.get("team_name") if participant.extra_data else None,
                rank=participant.final_rank,
                verification_code=secrets.token_urlsafe(16),
            )
            db.add(new_cert)
            await db.commit()
            await db.refresh(new_cert)
            certificates = [new_cert]
    
    # Build response with template info
    cert_list = []
    for c in certificates:
        # Get template for format info
        template_result = await db.execute(
            select(CertificateTemplate).where(CertificateTemplate.id == c.template_id)
        )
        template = template_result.scalar_one_or_none()
        output_format = template.output_format if template else "png"
        
        # Determine certificate type based on rank
        if c.rank:
            if c.rank <= 3:
                cert_type = "winner"
            elif c.rank <= 10:
                cert_type = "finalist"
            else:
                cert_type = "participation"
        else:
            cert_type = "participation"
        
        # Build file URL if file exists
        file_url = None
        if c.file_path:
            # Convert file path to URL
            file_url = f"/uploads/certificates/{c.verification_code}.{output_format}"
        
        cert_list.append({
            "id": str(c.id),
            "participant_id": str(c.participant_id),
            "event_id": str(participant.event_id),
            "event_name": event_name,
            "template_id": str(c.template_id) if c.template_id else None,
            "verification_code": c.verification_code,
            "certificate_type": cert_type,
            "file_url": file_url,
            "format": output_format,
            "display_name": c.display_name,
            "team_name": c.team_name,
            "rank": c.rank,
            "generated_at": c.generated_at.isoformat() if c.generated_at else None,
            "downloaded_at": c.downloaded_at.isoformat() if c.downloaded_at else None,
            "download_count": c.download_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    
    return cert_list


@router.get("/me/certificates/{cert_id}/download")
async def download_certificate(
    cert_id: str,
    format: str = "png",
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """
    Download a certificate.
    
    Generates the certificate on-the-fly if not already generated.
    Supports PDF and PNG formats.
    Rate limited to 10 downloads per minute per participant.
    """
    from uuid import UUID as PyUUID
    from fastapi.responses import FileResponse
    from app.models import CertificateTemplate
    from app.services.certificates import CertificateGenerator, CertificateData, TextZone, QRZone
    from app.config import get_settings
    import os
    
    settings = get_settings()
    
    # Rate limiting: 10 downloads per minute per participant
    rate_key = f"cert_download:{participant.id}:minute"
    current_count = await redis.incr(rate_key)
    if current_count == 1:
        await redis.expire(rate_key, 60)  # Expire after 1 minute
    
    if current_count > 10:
        # Log potential abuse
        audit_log = AuditLog(
            participant_id=participant.id,
            actor_type="participant",
            action="certificate_download_rate_limited",
            resource_type="certificate",
            extra_data={
                "cert_id": cert_id,
                "download_attempts": current_count,
            },
            success=False,
            error_message="Rate limit exceeded",
        )
        db.add(audit_log)
        await db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many download requests. Please wait a minute before trying again.",
        )
    
    try:
        cert_uuid = PyUUID(cert_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid certificate ID",
        )
    
    result = await db.execute(
        select(Certificate).where(
            Certificate.id == cert_uuid,
            Certificate.participant_id == participant.id,
        )
    )
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )
    
    # Get template first to check if regeneration needed
    result = await db.execute(
        select(CertificateTemplate).where(CertificateTemplate.id == certificate.template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate template not found",
        )
    
    # Check if we need to generate/regenerate the certificate
    # Regenerate if: no file, file doesn't exist, or template was updated after certificate was generated
    needs_regeneration = (
        not certificate.file_path or 
        not os.path.exists(certificate.file_path) or
        (certificate.generated_at and template.updated_at and template.updated_at > certificate.generated_at)
    )
    
    if needs_regeneration:
        # Check if template file exists
        template_path = template.template_file
        if template_path and not template_path.startswith("/"):
            template_path = os.path.join(settings.UPLOAD_DIR, template_path)
        
        if not template_path or not os.path.exists(template_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Certificate template image not found",
            )
        
        # Get event
        result = await db.execute(
            select(Event).where(Event.id == participant.event_id)
        )
        event = result.scalar_one_or_none()
        
        # Build text zones from template
        text_zones = []
        if template.text_zones:
            for zone_config in template.text_zones:
                text_zones.append(TextZone(
                    id=zone_config.get("id", ""),
                    field=zone_config.get("field", ""),
                    x=zone_config.get("x", 0),
                    y=zone_config.get("y", 0),
                    width=zone_config.get("width", 100),
                    height=zone_config.get("height", 50),
                    font_family=zone_config.get("font_family", "Helvetica"),
                    font_size=zone_config.get("font_size", 24),
                    font_color=zone_config.get("font_color") or zone_config.get("color", "#000000"),
                    alignment=zone_config.get("alignment", "center"),
                    is_percentage=zone_config.get("is_percentage", True),
                ))
        
        # Build QR zone
        qr_zone = None
        if template.qr_zone:
            qr_zone = QRZone(
                x=template.qr_zone.get("x", 0),
                y=template.qr_zone.get("y", 0),
                size=template.qr_zone.get("size", 100),
                is_percentage=template.qr_zone.get("is_percentage", True),
            )
        
        # Create certificate data
        cert_data = CertificateData(
            participant_id=certificate.participant_id,
            display_name=certificate.display_name or participant.name or participant.username or "Participant",
            team_name=certificate.team_name,
            rank=certificate.rank,
            score=participant.final_score,
            event_name=event.name if event else "Event",
        )
        
        # Generate certificate
        generator = CertificateGenerator()
        verify_url = f"{settings.app_url}/verify"
        
        result = generator.generate_png(
            template_path=template_path,
            data=cert_data,
            text_zones=text_zones,
            qr_zone=qr_zone,
            verification_url_base=verify_url,
        )
        
        if not result.success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate certificate: {result.error}",
            )
        
        # Update certificate record
        certificate.file_path = result.file_path
        certificate.generated_at = datetime.now(timezone.utc)
        await db.flush()
    
    # Update download tracking
    certificate.download_count += 1
    certificate.downloaded_at = datetime.now(timezone.utc)
    await db.commit()
    
    # Determine content type
    media_type = "application/pdf" if format == "pdf" else "image/png"
    filename = f"certificate_{certificate.verification_code}.{format}"
    
    return FileResponse(
        certificate.file_path,
        media_type=media_type,
        filename=filename,
    )


@router.patch("/me/certificates/{cert_id}")
async def update_certificate_display_name(
    cert_id: str,
    request: CertificateCustomizeRequest,
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """
    Update the display name on a certificate.
    
    Allows participants to customize how their name appears on the certificate.
    This will regenerate the certificate on next download.
    """
    from uuid import UUID as PyUUID
    from datetime import datetime, timezone
    import os
    
    try:
        cert_uuid = PyUUID(cert_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid certificate ID",
        )
    
    result = await db.execute(
        select(Certificate).where(
            Certificate.id == cert_uuid,
            Certificate.participant_id == participant.id,
        )
    )
    certificate = result.scalar_one_or_none()
    
    if not certificate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )
    
    # Update the display name
    certificate.display_name = request.display_name.strip()
    
    # Clear the file path to force regeneration on next download
    if certificate.file_path and os.path.exists(certificate.file_path):
        try:
            os.remove(certificate.file_path)
        except OSError:
            pass
    certificate.file_path = None
    certificate.generated_at = None
    
    await db.commit()
    
    return {
        "success": True,
        "message": "Display name updated successfully",
        "display_name": certificate.display_name,
    }
