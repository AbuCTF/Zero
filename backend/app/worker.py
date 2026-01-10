"""
ARQ Background Worker

Handles:
- Email campaign processing
- CTFd synchronization
- Certificate generation
- Cleanup tasks
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict
from uuid import UUID

from arq import create_pool, cron
from arq.connections import RedisSettings
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import (
    CampaignStatus,
    Certificate,
    CertificateTemplate,
    EmailCampaign,
    EmailLog,
    EmailProvider,
    EmailStatus,
    EmailTemplate,
    Event,
    Participant,
    Session as UserSession,
)
from app.services.email import EmailMessage, EmailOrchestrator, EmailTemplateRenderer
from app.services.certificates import CertificateGenerator, TextZone
from app.utils.security import decrypt_data

logger = logging.getLogger(__name__)
settings = get_settings()


# Create async engine and session factory for worker
engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Get a database session."""
    async with async_session() as session:
        yield session


async def get_providers_config(db: AsyncSession) -> list:
    """Get active email provider configurations."""
    result = await db.execute(
        select(EmailProvider)
        .where(EmailProvider.is_active == True)
        .order_by(EmailProvider.priority)
    )
    providers = result.scalars().all()
    
    configs = []
    for p in providers:
        # Decrypt sensitive config fields
        config = dict(p.config)
        sensitive_fields = ["password", "api_key", "smtp_password"]
        for field in sensitive_fields:
            if field in config and config[field]:
                try:
                    config[field] = decrypt_data(config[field])
                except Exception:
                    pass  # Not encrypted or decryption failed
        
        configs.append({
            "id": p.id,
            "name": p.name,
            "type": p.provider_type.value,
            "config": config,
            "priority": p.priority,
            "daily_limit": p.daily_limit,
            "hourly_limit": p.hourly_limit,
            "minute_limit": p.minute_limit,
            "second_limit": p.second_limit,
        })
    
    return configs


# =============================================================================
# Email Tasks
# =============================================================================


async def send_email_task(
    ctx: Dict[str, Any],
    to: str,
    subject: str,
    body_html: str,
    body_text: str = None,
    participant_id: str = None,
    campaign_id: str = None,
    template_id: str = None,
):
    """Send a single email."""
    redis = ctx["redis"]
    
    async with async_session() as db:
        providers = await get_providers_config(db)
        
        if not providers:
            logger.error("No active email providers configured")
            return {"success": False, "error": "No providers"}
        
        orchestrator = EmailOrchestrator(redis)
        
        message = EmailMessage(
            to=to,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )
        
        result = await orchestrator.send(message, providers)
        
        # Log the email
        email_log = EmailLog(
            participant_id=UUID(participant_id) if participant_id else None,
            campaign_id=UUID(campaign_id) if campaign_id else None,
            template_id=UUID(template_id) if template_id else None,
            provider_id=result.provider_id,
            recipient=to,
            subject=subject,
            status=EmailStatus.SENT if result.success else EmailStatus.FAILED,
            external_id=result.message_id,
            error_message=result.error,
            sent_at=datetime.utcnow() if result.success else None,
        )
        
        db.add(email_log)
        await db.commit()
        
        return {
            "success": result.success,
            "message_id": result.message_id,
            "error": result.error,
        }


async def process_campaign_task(ctx: Dict[str, Any], campaign_id: str):
    """Process an email campaign - send emails to all recipients."""
    redis = ctx["redis"]
    campaign_uuid = UUID(campaign_id)
    
    async with async_session() as db:
        # Get campaign
        result = await db.execute(
            select(EmailCampaign).where(EmailCampaign.id == campaign_uuid)
        )
        campaign = result.scalar_one_or_none()
        
        if not campaign:
            logger.error(f"Campaign {campaign_id} not found")
            return
        
        if campaign.status not in [EmailStatus.PENDING, EmailStatus.PROCESSING]:
            logger.info(f"Campaign {campaign_id} status is {campaign.status}, skipping")
            return
        
        # Update status to processing
        campaign.status = EmailStatus.PROCESSING
        await db.commit()
        
        # Get template
        result = await db.execute(
            select(EmailTemplate).where(EmailTemplate.id == campaign.template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            campaign.status = EmailStatus.FAILED
            await db.commit()
            logger.error(f"Template not found for campaign {campaign_id}")
            return
        
        # Get providers
        providers = await get_providers_config(db)
        if not providers:
            campaign.status = EmailStatus.FAILED
            await db.commit()
            logger.error("No active email providers")
            return
        
        # Build recipient query
        query = select(Participant)
        
        if campaign.event_id:
            query = query.where(Participant.event_id == campaign.event_id)
        
        criteria = campaign.filter_criteria or {}
        if criteria.get("verified_only"):
            query = query.where(Participant.email_verified == True)
        if criteria.get("unverified_only"):
            query = query.where(Participant.email_verified == False)
        
        result = await db.execute(query)
        participants = result.scalars().all()
        
        renderer = EmailTemplateRenderer()
        orchestrator = EmailOrchestrator(redis)
        
        sent = 0
        failed = 0
        
        for participant in participants:
            # Check if campaign was cancelled
            await db.refresh(campaign)
            if campaign.status == EmailStatus.FAILED:
                logger.info(f"Campaign {campaign_id} was cancelled")
                break
            
            # Prepare context
            context = {
                "name": participant.name or participant.username,
                "email": participant.email,
                "username": participant.username,
            }
            
            # Render email
            subject, body_html, body_text = renderer.render(
                template.subject,
                template.body_html,
                template.body_text,
                context,
            )
            
            message = EmailMessage(
                to=participant.email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )
            
            # Send
            send_result = await orchestrator.send(message, providers)
            
            # Log
            email_log = EmailLog(
                participant_id=participant.id,
                campaign_id=campaign.id,
                template_id=template.id,
                provider_id=send_result.provider_id,
                recipient=participant.email,
                subject=subject,
                status=EmailStatus.SENT if send_result.success else EmailStatus.FAILED,
                external_id=send_result.message_id,
                error_message=send_result.error,
                sent_at=datetime.utcnow() if send_result.success else None,
            )
            db.add(email_log)
            
            if send_result.success:
                sent += 1
            else:
                failed += 1
            
            # Update campaign progress
            campaign.sent_count = sent
            campaign.failed_count = failed
            
            # Commit periodically
            if (sent + failed) % 10 == 0:
                await db.commit()
            
            # Small delay to avoid overwhelming providers
            await asyncio.sleep(0.1)
        
        # Final update
        campaign.status = EmailStatus.SENT
        campaign.completed_at = datetime.utcnow()
        await db.commit()
        
        logger.info(f"Campaign {campaign_id} completed: {sent} sent, {failed} failed")


async def send_verification_email_task(
    ctx: Dict[str, Any],
    participant_id: str,
    verification_url: str,
):
    """Send email verification to a participant."""
    redis = ctx["redis"]
    
    async with async_session() as db:
        # Get participant
        result = await db.execute(
            select(Participant).where(Participant.id == UUID(participant_id))
        )
        participant = result.scalar_one_or_none()
        
        if not participant:
            logger.error(f"Participant {participant_id} not found")
            return
        
        # Get event
        result = await db.execute(
            select(Event).where(Event.id == participant.event_id)
        )
        event = result.scalar_one_or_none()
        
        # Try to find template
        result = await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.event_id == participant.event_id,
                EmailTemplate.template_type == "verification",
                EmailTemplate.is_active == True,
            )
        )
        template = result.scalar_one_or_none()
        
        # Fall back to global template
        if not template:
            result = await db.execute(
                select(EmailTemplate).where(
                    EmailTemplate.event_id.is_(None),
                    EmailTemplate.template_type == "verification",
                    EmailTemplate.is_active == True,
                )
            )
            template = result.scalar_one_or_none()
        
        renderer = EmailTemplateRenderer()
        
        context = {
            "name": participant.name or participant.username,
            "email": participant.email,
            "username": participant.username,
            "event_name": event.name if event else "Event",
            "verification_url": verification_url,
        }
        
        if template:
            subject, body_html, body_text = renderer.render(
                template.subject,
                template.body_html,
                template.body_text,
                context,
            )
        else:
            # Use default template
            subject, body_html, body_text = renderer.render_default(
                "verification", context
            )
        
        providers = await get_providers_config(db)
        
        if not providers:
            logger.error("No active email providers")
            return
        
        orchestrator = EmailOrchestrator(redis)
        
        message = EmailMessage(
            to=participant.email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )
        
        result = await orchestrator.send(message, providers)
        
        # Log
        email_log = EmailLog(
            participant_id=participant.id,
            template_id=template.id if template else None,
            provider_id=result.provider_id,
            recipient=participant.email,
            subject=subject,
            status=EmailStatus.SENT if result.success else EmailStatus.FAILED,
            external_id=result.message_id,
            error_message=result.error,
            sent_at=datetime.utcnow() if result.success else None,
        )
        db.add(email_log)
        await db.commit()
        
        if result.success:
            logger.info(f"Verification email sent to {participant.email}")
        else:
            logger.error(f"Failed to send verification to {participant.email}: {result.error}")


# =============================================================================
# Certificate Tasks
# =============================================================================


async def generate_certificate_task(
    ctx: Dict[str, Any],
    certificate_id: str,
    output_format: str = "png",
):
    """Generate a certificate for a participant."""
    async with async_session() as db:
        # Get certificate
        result = await db.execute(
            select(Certificate).where(Certificate.id == UUID(certificate_id))
        )
        cert = result.scalar_one_or_none()
        
        if not cert:
            logger.error(f"Certificate {certificate_id} not found")
            return
        
        # Get template
        result = await db.execute(
            select(CertificateTemplate).where(CertificateTemplate.id == cert.template_id)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            logger.error(f"Template not found for certificate {certificate_id}")
            return
        
        # Get participant
        result = await db.execute(
            select(Participant).where(Participant.id == cert.participant_id)
        )
        participant = result.scalar_one_or_none()
        
        if not participant:
            logger.error(f"Participant not found for certificate {certificate_id}")
            return
        
        # Get event
        result = await db.execute(
            select(Event).where(Event.id == participant.event_id)
        )
        event = result.scalar_one_or_none()
        
        # Build text zones
        text_zones = []
        for zone_config in template.text_zones:
            zone = TextZone(
                text=zone_config.get("text", "").format(
                    name=participant.name or participant.username,
                    username=participant.username,
                    rank=participant.final_rank or "-",
                    score=participant.final_score or 0,
                    event_name=event.name if event else "",
                    event_date=event.event_start.strftime("%B %d, %Y") if event and event.event_start else "",
                ),
                x=zone_config.get("x", 0),
                y=zone_config.get("y", 0),
                font_name=zone_config.get("font_name", "Helvetica"),
                font_size=zone_config.get("font_size", 24),
                color=zone_config.get("color", "#000000"),
                align=zone_config.get("align", "left"),
            )
            text_zones.append(zone)
        
        # Generate certificate
        generator = CertificateGenerator()
        
        verify_url = f"{settings.app_url}/verify/{cert.verification_code}"
        
        if output_format == "pdf":
            output_path = await generator.generate_pdf(
                template_path=template.template_path,
                output_path=f"{settings.UPLOAD_DIR}/certificates/{certificate_id}.pdf",
                text_zones=text_zones,
                qr_data=verify_url if template.qr_zone else None,
                qr_zone=template.qr_zone,
            )
        else:
            output_path = await generator.generate_png(
                template_path=template.template_path,
                output_path=f"{settings.UPLOAD_DIR}/certificates/{certificate_id}.png",
                text_zones=text_zones,
                qr_data=verify_url if template.qr_zone else None,
                qr_zone=template.qr_zone,
            )
        
        # Update certificate record
        cert.generated_at = datetime.utcnow()
        cert.file_path = output_path
        await db.commit()
        
        logger.info(f"Certificate {certificate_id} generated: {output_path}")


async def bulk_generate_certificates_task(
    ctx: Dict[str, Any],
    event_id: str,
    output_format: str = "png",
):
    """Generate certificates for all eligible participants in an event."""
    async with async_session() as db:
        # Get certificates that need generation
        result = await db.execute(
            select(Certificate)
            .join(Participant, Certificate.participant_id == Participant.id)
            .where(
                Participant.event_id == UUID(event_id),
                Certificate.generated_at.is_(None),
            )
        )
        certificates = result.scalars().all()
        
        for cert in certificates:
            await generate_certificate_task(ctx, str(cert.id), output_format)
        
        logger.info(f"Generated {len(certificates)} certificates for event {event_id}")


# =============================================================================
# CTFd Sync Tasks
# =============================================================================


async def sync_ctfd_results_task(ctx: Dict[str, Any], event_id: str):
    """Sync results from CTFd."""
    from app.services.ctfd import CTFdClient, CTFdSyncService
    
    async with async_session() as db:
        result = await db.execute(
            select(Event).where(Event.id == UUID(event_id))
        )
        event = result.scalar_one_or_none()
        
        if not event or not event.ctfd_url or not event.ctfd_api_key:
            logger.error(f"Event {event_id} not found or missing CTFd config")
            return
        
        api_key = decrypt_data(event.ctfd_api_key)
        client = CTFdClient(event.ctfd_url, api_key)
        sync_service = CTFdSyncService(db, client)
        
        try:
            results = await sync_service.sync_results(UUID(event_id))
            event.ctfd_synced_at = datetime.utcnow()
            await db.commit()
            logger.info(f"Synced {len(results)} results from CTFd for event {event_id}")
        except Exception as e:
            logger.error(f"CTFd sync failed for event {event_id}: {e}")


# =============================================================================
# Cleanup Tasks
# =============================================================================


async def cleanup_expired_sessions_task(ctx: Dict[str, Any]):
    """Remove expired sessions."""
    async with async_session() as db:
        result = await db.execute(
            select(UserSession).where(UserSession.expires_at < datetime.utcnow())
        )
        sessions = result.scalars().all()
        
        for session in sessions:
            await db.delete(session)
        
        await db.commit()
        
        if sessions:
            logger.info(f"Cleaned up {len(sessions)} expired sessions")


async def cleanup_old_email_logs_task(ctx: Dict[str, Any]):
    """Remove email logs older than 90 days."""
    cutoff = datetime.utcnow() - timedelta(days=90)
    
    async with async_session() as db:
        result = await db.execute(
            select(EmailLog).where(EmailLog.sent_at < cutoff)
        )
        logs = result.scalars().all()
        
        for log in logs:
            await db.delete(log)
        
        await db.commit()
        
        if logs:
            logger.info(f"Cleaned up {len(logs)} old email logs")


# =============================================================================
# Scheduled Tasks (Cron)
# =============================================================================


async def process_pending_campaigns(ctx: Dict[str, Any]):
    """Check for scheduled campaigns and process them."""
    async with async_session() as db:
        result = await db.execute(
            select(EmailCampaign).where(
                EmailCampaign.status == CampaignStatus.SCHEDULED,
                (EmailCampaign.scheduled_for.is_(None)) |
                (EmailCampaign.scheduled_for <= datetime.utcnow()),
            )
        )
        campaigns = result.scalars().all()
        
        for campaign in campaigns:
            await process_campaign_task(ctx, str(campaign.id))


async def auto_sync_ctfd(ctx: Dict[str, Any]):
    """Auto-sync CTFd results for active events."""
    async with async_session() as db:
        result = await db.execute(
            select(Event).where(
                Event.status == "live",
                Event.ctfd_url.isnot(None),
                Event.ctfd_api_key.isnot(None),
            )
        )
        events = result.scalars().all()
        
        for event in events:
            # Only sync if last sync was > 5 minutes ago
            if event.ctfd_synced_at:
                if datetime.utcnow() - event.ctfd_synced_at < timedelta(minutes=5):
                    continue
            
            await sync_ctfd_results_task(ctx, str(event.id))


# =============================================================================
# Bulk Import Task
# =============================================================================


async def bulk_import_participants_task(
    ctx: Dict[str, Any],
    event_id: str,
    participants_data: list,
    generate_passwords: bool = True,
    update_existing: bool = True,
    job_id: str = None,
):
    """
    Background task to import large numbers of participants.
    Optimized for bulk operations - fetches all existing data upfront.
    """
    import json
    import secrets
    from app.utils.security import hash_password
    
    redis = ctx.get("redis")
    progress_key = f"import_progress:{job_id or event_id}"
    
    async def update_progress(imported: int, updated: int, skipped: int, errors_list: list, total: int, status: str = "processing"):
        if redis:
            processed = imported + updated + skipped + len(errors_list)
            progress_pct = min(100, int((processed / total) * 100)) if total > 0 else 0
            await redis.hset(progress_key, mapping={
                "imported": imported,
                "updated": updated,
                "skipped": skipped,
                "errors": json.dumps(errors_list[:50]),
                "total": total,
                "status": status,
                "progress": progress_pct,
            })
            await redis.expire(progress_key, 3600)
    
    total = len(participants_data)
    await update_progress(0, 0, 0, [], total, "starting")
    
    imported = 0
    updated = 0
    skipped = 0
    errors_list = []
    
    try:
        async with async_session() as db:
            event_uuid = UUID(event_id)
            
            # OPTIMIZATION: Fetch ALL existing participants for this event upfront
            logger.info(f"Fetching existing participants for event {event_id}...")
            result = await db.execute(
                select(Participant).where(Participant.event_id == event_uuid)
            )
            existing_participants = result.scalars().all()
            
            # Build lookup dictionaries - O(1) lookup instead of O(n) database queries
            existing_by_email = {p.email.lower(): p for p in existing_participants}
            existing_usernames = {p.username.lower() for p in existing_participants}
            
            logger.info(f"Found {len(existing_by_email)} existing participants, processing {total} new records...")
            
            await update_progress(0, 0, 0, [], total, "processing")
            
            # Batch for new participants
            new_participants = []
            
            for i, p_data in enumerate(participants_data):
                email = (p_data.get("email") or "").strip().lower()
                
                if not email or "@" not in email:
                    errors_list.append({"row": i + 1, "error": "Invalid email"})
                    continue
                
                try:
                    # Check if exists using in-memory lookup (O(1) instead of database query)
                    existing = existing_by_email.get(email)
                    
                    if existing:
                        if update_existing:
                            was_updated = False
                            
                            if p_data.get("name") and p_data["name"] != existing.name:
                                existing.name = p_data["name"]
                                was_updated = True
                            
                            if p_data.get("rank"):
                                try:
                                    new_rank = int(p_data["rank"])
                                    if new_rank != existing.final_rank:
                                        existing.final_rank = new_rank
                                        was_updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            if p_data.get("score"):
                                try:
                                    new_score = float(p_data["score"])
                                    if new_score != existing.final_score:
                                        existing.final_score = new_score
                                        was_updated = True
                                except (ValueError, TypeError):
                                    pass
                            
                            if was_updated:
                                updated += 1
                            else:
                                skipped += 1
                        else:
                            skipped += 1
                        
                        # Update progress every 500 records
                        if (imported + updated + skipped) % 500 == 0:
                            await update_progress(imported, updated, skipped, errors_list, total)
                        continue
                    
                    # Generate unique username using in-memory set
                    base_username = (p_data.get("username") or email.split("@")[0]).lower()
                    username = base_username
                    counter = 1
                    while username in existing_usernames:
                        username = f"{base_username}{counter}"
                        counter += 1
                    
                    # Add to set so next iteration knows it's taken
                    existing_usernames.add(username)
                    
                    password = secrets.token_urlsafe(12) if generate_passwords else "changeme123"
                    
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
                    
                    extra_data = {}
                    if p_data.get("team_name"):
                        extra_data["team_name"] = p_data["team_name"]
                    if p_data.get("_extra"):
                        extra_data.update(p_data["_extra"])
                    
                    participant = Participant(
                        event_id=event_uuid,
                        email=email,
                        username=username,
                        password_hash=hash_password(password),
                        name=p_data.get("name") or email.split("@")[0],
                        final_rank=final_rank,
                        final_score=final_score,
                        extra_data=extra_data,
                        email_verified=True,
                        email_verified_at=datetime.utcnow(),
                        source="import",
                    )
                    
                    new_participants.append(participant)
                    # Also add to email lookup so duplicates in same CSV are caught
                    existing_by_email[email] = participant
                    imported += 1
                    
                    # Batch insert every 500 new participants
                    if len(new_participants) >= 500:
                        db.add_all(new_participants)
                        await db.commit()
                        new_participants = []
                        await update_progress(imported, updated, skipped, errors_list, total)
                    
                except Exception as e:
                    errors_list.append({"row": i + 1, "email": email, "error": str(e)})
            
            # Insert remaining participants
            if new_participants:
                db.add_all(new_participants)
            
            # Final commit for all updates and remaining inserts
            await db.commit()
        
        await update_progress(imported, updated, skipped, errors_list, total, "completed")
        
        logger.info(f"Import completed: {imported} imported, {updated} updated, {skipped} skipped, {len(errors_list)} errors")
        
        return {
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "errors": errors_list[:50],
            "total_errors": len(errors_list),
        }
    
    except Exception as e:
        logger.error(f"Import task failed: {e}")
        await update_progress(imported, updated, skipped, errors_list, total, "failed")
        if redis:
            await redis.hset(progress_key, "error", str(e))
        raise


# =============================================================================
# Worker Configuration
# =============================================================================


async def startup(ctx: Dict[str, Any]):
    """Worker startup."""
    logger.info("ARQ Worker starting up")
    ctx["redis"] = await create_pool(parse_redis_url(settings.redis_url))


async def shutdown(ctx: Dict[str, Any]):
    """Worker shutdown."""
    logger.info("ARQ Worker shutting down")
    if "redis" in ctx:
        await ctx["redis"].close()


def parse_redis_url(url: str) -> RedisSettings:
    """Parse Redis URL into RedisSettings."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int(parsed.path.lstrip("/") or 0),
    )


class WorkerSettings:
    """ARQ worker settings."""
    
    redis_settings = parse_redis_url(settings.redis_url)
    
    functions = [
        send_email_task,
        process_campaign_task,
        send_verification_email_task,
        generate_certificate_task,
        bulk_generate_certificates_task,
        sync_ctfd_results_task,
        cleanup_expired_sessions_task,
        cleanup_old_email_logs_task,
        bulk_import_participants_task,
    ]
    
    cron_jobs = [
        # Process pending campaigns every minute
        cron(process_pending_campaigns, minute={0, 15, 30, 45}),
        # Auto-sync CTFd every 10 minutes
        cron(auto_sync_ctfd, minute={0, 10, 20, 30, 40, 50}),
        # Cleanup expired sessions daily at 3am
        cron(cleanup_expired_sessions_task, hour=3, minute=0),
        # Cleanup old email logs weekly on Sunday at 4am
        cron(cleanup_old_email_logs_task, weekday=6, hour=4, minute=0),
    ]
    
    on_startup = startup
    on_shutdown = shutdown
    
    # Allow jobs to run for up to 1 hour
    job_timeout = 3600
    
    # Keep results for 1 day
    keep_result = 86400
    
    # Retry failed jobs
    max_tries = 3
    
    # Health check key
    health_check_key = "arq:health"
    health_check_interval = 60
