"""
Certificates API Routes

Endpoints for generating and verifying certificates.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_client_ip, require_verified_participant
from app.config import get_settings
from app.database import get_session
from app.models import (
    AuditLog,
    Certificate,
    CertificateTemplate,
    Event,
    Participant,
    Team,
    TeamMember,
)
from app.schemas import (
    BaseResponse,
    CertificateCustomizeRequest,
    CertificatePreviewRequest,
    CertificateResponse,
    CertificateVerifyResponse,
)
from app.services.certificates import CertificateData, CertificateGenerator

router = APIRouter()
settings = get_settings()


@router.get("")
async def list_certificates(
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """List all certificates for the current participant."""
    result = await db.execute(
        select(Certificate)
        .where(Certificate.participant_id == participant.id)
        .order_by(Certificate.created_at.desc())
    )
    certificates = result.scalars().all()
    
    return {
        "certificates": [
            {
                "id": str(c.id),
                "display_name": c.display_name,
                "team_name": c.team_name,
                "rank": c.rank,
                "verification_code": c.verification_code,
                "generated_at": c.generated_at.isoformat() if c.generated_at else None,
                "download_count": c.download_count,
            }
            for c in certificates
        ]
    }


@router.get("/available")
async def get_available_certificates(
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """
    Get certificate templates available for this participant.
    
    Based on their rank, different templates may be available.
    """
    # Get event
    result = await db.execute(
        select(Event).where(Event.id == participant.event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event or event.status.value not in ["ended", "archived"]:
        return {"templates": [], "message": "Certificates not yet available"}
    
    # Get templates for this event
    result = await db.execute(
        select(CertificateTemplate)
        .where(
            CertificateTemplate.event_id == event.id,
            CertificateTemplate.is_active == True,
        )
        .order_by(CertificateTemplate.rank_from.asc().nullsfirst())
    )
    templates = result.scalars().all()
    
    # Filter by participant's rank
    available = []
    for t in templates:
        if t.rank_from is None and t.rank_to is None:
            # Generic template, available to all
            available.append(t)
        elif participant.final_rank:
            if t.rank_from and t.rank_to:
                if t.rank_from <= participant.final_rank <= t.rank_to:
                    available.append(t)
    
    return {
        "rank": participant.final_rank,
        "templates": [
            {
                "id": str(t.id),
                "name": t.name,
                "description": t.description,
                "rank_range": f"{t.rank_from or 1}-{t.rank_to or '∞'}" if t.rank_from or t.rank_to else "All",
            }
            for t in available
        ],
    }


@router.post("/customize", response_model=CertificateResponse)
async def customize_certificate(
    data: CertificateCustomizeRequest,
    template_id: str,
    request: Request,
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """
    Customize and generate a certificate.
    
    Allows participant to set their display name (as it will appear on cert).
    """
    # Get template
    result = await db.execute(
        select(CertificateTemplate).where(
            CertificateTemplate.id == template_id,
            CertificateTemplate.is_active == True,
        )
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate template not found",
        )
    
    # Verify participant can use this template
    if template.rank_from or template.rank_to:
        if participant.final_rank:
            if template.rank_from and participant.final_rank < template.rank_from:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not eligible for this certificate",
                )
            if template.rank_to and participant.final_rank > template.rank_to:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not eligible for this certificate",
                )
    
    # Get team name if in team
    team_name = None
    result = await db.execute(
        select(TeamMember).where(TeamMember.participant_id == participant.id)
    )
    membership = result.scalar_one_or_none()
    
    if membership:
        result = await db.execute(
            select(Team).where(Team.id == membership.team_id)
        )
        team = result.scalar_one_or_none()
        if team:
            team_name = team.name
    
    # Check if certificate already exists for this template
    result = await db.execute(
        select(Certificate).where(
            Certificate.participant_id == participant.id,
            Certificate.template_id == template.id,
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update display name
        existing.display_name = data.display_name
        existing.team_name = team_name
        cert = existing
    else:
        # Generate verification code
        from app.utils.security import generate_certificate_code
        
        verification_code = generate_certificate_code(
            str(participant.id),
            "winner" if participant.final_rank and participant.final_rank <= 15 else "participation",
            datetime.utcnow(),
        )
        
        # Create certificate record
        cert = Certificate(
            participant_id=participant.id,
            template_id=template.id,
            display_name=data.display_name,
            team_name=team_name,
            rank=participant.final_rank,
            verification_code=verification_code,
        )
        db.add(cert)
    
    await db.flush()
    
    # Generate the certificate file
    generator = CertificateGenerator()
    
    # Get event for name
    result = await db.execute(
        select(Event).where(Event.id == template.event_id)
    )
    event = result.scalar_one_or_none()
    
    cert_data = CertificateData(
        participant_id=participant.id,
        display_name=data.display_name,
        team_name=team_name,
        rank=participant.final_rank,
        score=participant.final_score,
        event_name=event.name if event else "",
        issued_at=datetime.utcnow(),
    )
    
    template_path = Path(settings.upload_dir) / template.template_file
    
    result = generator.generate(
        str(template_path),
        cert_data,
        template.text_zones,
        template.qr_zone,
        output_format=template.output_format,
        verification_url_base=f"{settings.app_url}/verify",
    )
    
    if result.success:
        cert.file_path = result.file_path
        cert.generated_at = datetime.utcnow()
        await db.flush()
        
        # Log generation
        audit_log = AuditLog(
            action="certificate.generate",
            participant_id=participant.id,
            actor_type="participant",
            resource_type="certificate",
            resource_id=cert.id,
            ip_address=get_client_ip(request),
        )
        db.add(audit_log)
        await db.flush()
    
    return CertificateResponse(
        id=cert.id,
        display_name=cert.display_name,
        team_name=cert.team_name,
        rank=cert.rank,
        verification_code=cert.verification_code,
        generated_at=cert.generated_at,
        download_count=cert.download_count,
    )


@router.get("/download/{verification_code}")
async def download_certificate(
    verification_code: str,
    request: Request,
    participant: Participant = Depends(require_verified_participant),
    db: AsyncSession = Depends(get_session),
):
    """Download a generated certificate."""
    result = await db.execute(
        select(Certificate).where(
            Certificate.verification_code == verification_code,
            Certificate.participant_id == participant.id,
        )
    )
    cert = result.scalar_one_or_none()
    
    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate not found",
        )
    
    if not cert.file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate not yet generated",
        )
    
    file_path = Path(cert.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate file not found",
        )
    
    # Update download count
    cert.download_count += 1
    if not cert.downloaded_at:
        cert.downloaded_at = datetime.utcnow()
    
    await db.flush()
    
    # Log download
    audit_log = AuditLog(
        action="certificate.download",
        participant_id=participant.id,
        actor_type="participant",
        resource_type="certificate",
        resource_id=cert.id,
        ip_address=get_client_ip(request),
    )
    db.add(audit_log)
    await db.flush()
    
    # Determine media type
    if file_path.suffix == ".pdf":
        media_type = "application/pdf"
    else:
        media_type = "image/png"
    
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=f"certificate-{verification_code}{file_path.suffix}",
    )


# =============================================================================
# Public Verification
# =============================================================================


@router.get("/verify/{code}", response_model=CertificateVerifyResponse)
async def verify_certificate(
    code: str,
    db: AsyncSession = Depends(get_session),
):
    """
    Publicly verify a certificate by its code.
    
    This endpoint is public and does not require authentication.
    """
    result = await db.execute(
        select(Certificate).where(Certificate.verification_code == code)
    )
    cert = result.scalar_one_or_none()
    
    if not cert:
        return CertificateVerifyResponse(valid=False)
    
    # Get participant for basic info
    result = await db.execute(
        select(Participant).where(Participant.id == cert.participant_id)
    )
    participant = result.scalar_one_or_none()
    
    # Get event name
    event_name = None
    if participant:
        result = await db.execute(
            select(Event).where(Event.id == participant.event_id)
        )
        event = result.scalar_one_or_none()
        if event:
            event_name = event.name
    
    # Log verification
    audit_log = AuditLog(
        action="certificate.verify",
        actor_type="system",
        resource_type="certificate",
        resource_id=cert.id,
        metadata={"verification_code": code},
    )
    db.add(audit_log)
    await db.flush()
    
    return CertificateVerifyResponse(
        valid=True,
        participant_name=cert.display_name,
        team_name=cert.team_name,
        rank=cert.rank,
        event_name=event_name,
        issued_at=cert.generated_at,
    )
