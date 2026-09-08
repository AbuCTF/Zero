"""
Authentication API Routes

Handles:
- Admin user login/logout
- Participant registration and login
- Email verification
- Password reset
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    create_session,
    delete_session,
    get_client_ip,
    get_current_participant,
    get_current_session,
    get_current_user,
    get_redis,
    get_user_agent,
    require_participant,
    require_user,
)
from app.config import get_settings
from app.database import get_session
from app.models import (
    AuditLog,
    EmailLog,
    EmailStatus,
    Event,
    EventStatus,
    Participant,
    Session,
    User,
)
from app.schemas import (
    AuthResponse,
    BaseResponse,
    LoginRequest,
    RegisterRequest,
    ResendVerificationRequest,
    VerifyEmailRequest,
)
from app.services.email import EmailMessage, EmailOrchestrator, render_email, render_subject
from app.utils import discord as discord_oauth
from app.utils.ratelimit import rate_limit
from app.utils.security import (
    generate_verification_token,
    hash_password,
    is_valid_email,
    is_valid_username,
    verify_password,
)
from app.utils.turnstile import verify_turnstile

import logging

logger = logging.getLogger(__name__)

router = APIRouter()
settings = get_settings()


# =============================================================================
# Admin User Authentication
# =============================================================================


async def _is_admin_login_locked(redis, user_id, ip: str) -> bool:
    """
    Return True if the given (admin user, IP) pair — or the IP as a whole — is
    currently locked out from logging in.

    The hard lock is keyed by (user_id, ip) so that an attacker from one IP can
    never lock the real admin out globally; a separate, higher-threshold per-IP
    counter blunts a single IP hammering many accounts.

    Fails open (returns False) on any Redis error.
    """
    if redis is None:
        return False
    try:
        if await redis.get(f"login_lock:user:{user_id}:ip:{ip}"):
            return True
        ip_count = await redis.get(f"login_fail:ip:{ip}")
        if ip_count is not None:
            try:
                if int(ip_count) >= settings.max_login_attempts * 10:
                    return True
            except (TypeError, ValueError):
                pass
        return False
    except Exception as exc:  # noqa: BLE001 - fail open on Redis error
        logger.warning("Admin lockout check failed (fail-open): %s", exc)
        return False


async def _register_admin_login_failure(redis, user_id, ip: str) -> bool:
    """
    Record a failed admin login attempt for (user_id, ip).

    Returns True only on the failure that *crosses* the lockout threshold, so the
    caller writes exactly one ``account.locked`` audit record. Fails open
    (returns False) on any Redis error.
    """
    if redis is None:
        return False
    try:
        window = settings.lockout_duration_minutes * 60
        user_key = f"login_fail:user:{user_id}:ip:{ip}"
        user_count = await redis.incr(user_key)
        if user_count == 1:
            await redis.expire(user_key, window)

        ip_key = f"login_fail:ip:{ip}"
        ip_count = await redis.incr(ip_key)
        if ip_count == 1:
            await redis.expire(ip_key, window)

        if user_count >= settings.max_login_attempts:
            await redis.setex(f"login_lock:user:{user_id}:ip:{ip}", window, "1")
            return user_count == settings.max_login_attempts
        return False
    except Exception as exc:  # noqa: BLE001 - fail open on Redis error
        logger.warning("Admin login-failure tracking failed (fail-open): %s", exc)
        return False


async def _clear_admin_login_failures(redis, user_id, ip: str) -> None:
    """Clear all admin lockout counters/flags for (user_id, ip) after success."""
    if redis is None:
        return
    try:
        await redis.delete(
            f"login_lock:user:{user_id}:ip:{ip}",
            f"login_fail:user:{user_id}:ip:{ip}",
            f"login_fail:ip:{ip}",
        )
    except Exception as exc:  # noqa: BLE001 - fail open on Redis error
        logger.warning("Clearing admin lockout counters failed: %s", exc)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit("auth:login", (10, 60)))],
)
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """
    Login for admin users and participants.

    Determines account type by checking users table first, then participants.
    """
    # Verify captcha (no-op unless Turnstile is configured)
    await verify_turnstile(data.turnstile_token, get_client_ip(request))

    # Try to find admin user
    result = await db.execute(
        select(User).where(User.email == data.email.lower())
    )
    user = result.scalar_one_or_none()
    
    if user:
        client_ip = get_client_ip(request) or "unknown"

        # Enforce lockout before checking the password
        if await _is_admin_login_locked(redis, user.id, client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked. Try again later.",
            )

        # Verify password
        if not verify_password(data.password, user.password_hash):
            # Track the failure; True only when this attempt crosses the threshold
            just_locked = await _register_admin_login_failure(
                redis, user.id, client_ip
            )

            # Log failed attempt
            await _log_audit(
                db,
                action="account.login_failed",
                user_id=user.id,
                ip_address=client_ip,
                metadata={"reason": "invalid_password"},
            )

            if just_locked:
                lock_log = AuditLog(
                    action="account.locked",
                    user_id=user.id,
                    actor_type="user",
                    resource_type="user",
                    resource_id=user.id,
                    ip_address=client_ip,
                    success=False,
                    extra_data={
                        "reason": "too_many_failed_attempts",
                        "ip": client_ip,
                        "threshold": settings.max_login_attempts,
                        "lockout_minutes": settings.lockout_duration_minutes,
                    },
                )
                db.add(lock_log)
                await db.flush()

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is disabled",
            )
        
        # Create session
        session_id = await create_session(
            db,
            user_id=user.id,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        
        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await db.flush()

        # Clear any lockout counters for this account/IP on success
        await _clear_admin_login_failures(redis, user.id, client_ip)

        # Log success
        await _log_audit(
            db,
            action="account.login",
            user_id=user.id,
            ip_address=client_ip,
        )
        
        # Set cookie
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_id,
            httponly=settings.session_cookie_httponly,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
            max_age=settings.session_lifetime_hours * 3600,
        )
        
        return AuthResponse(
            success=True,
            message="Login successful",
            user={
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "name": user.name,
                "role": user.role.value,
            },
        )
    
    # Try to find participant (needs event context in real scenario)
    # For now, search across all events
    result = await db.execute(
        select(Participant).where(Participant.email == data.email.lower())
    )
    participant = result.scalar_one_or_none()
    
    if participant:
        # Check lockout
        if participant.locked_until and participant.locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Account temporarily locked. Try again later.",
            )
        
        # Verify password
        if not verify_password(data.password, participant.password_hash):
            # Increment failed attempts
            participant.login_attempts += 1
            
            if participant.login_attempts >= settings.max_login_attempts:
                participant.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.lockout_duration_minutes
                )
            
            await db.flush()
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        if participant.is_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is blocked",
            )
        
        # Reset login attempts on success
        participant.login_attempts = 0
        participant.locked_until = None
        
        # Create session
        session_id = await create_session(
            db,
            participant_id=participant.id,
            ip_address=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        
        await db.flush()
        
        # Log success
        await _log_audit(
            db,
            action="account.login",
            participant_id=participant.id,
            ip_address=get_client_ip(request),
        )
        
        # Set cookie
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_id,
            httponly=settings.session_cookie_httponly,
            secure=settings.session_cookie_secure,
            samesite=settings.session_cookie_samesite,
            max_age=settings.session_lifetime_hours * 3600,
        )
        
        return AuthResponse(
            success=True,
            message="Login successful",
            participant={
                "id": str(participant.id),
                "email": participant.email,
                "username": participant.username,
                "name": participant.name,
                "email_verified": participant.email_verified,
            },
        )
    
    # Neither found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )


@router.post("/logout", response_model=BaseResponse)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_session),
    session: Session = Depends(get_current_session),
):
    """Logout current user/participant."""
    if session:
        await delete_session(db, session.id)
    
    response.delete_cookie(settings.session_cookie_name)
    
    return BaseResponse(success=True, message="Logged out successfully")


@router.get("/me", response_model=AuthResponse)
async def get_me(
    user: User = Depends(get_current_user),
    participant: Participant = Depends(get_current_participant),
):
    """Get current authenticated user/participant."""
    if user:
        return AuthResponse(
            success=True,
            user={
                "id": str(user.id),
                "email": user.email,
                "username": user.username,
                "name": user.name,
                "role": user.role.value,
            },
        )
    
    if participant:
        return AuthResponse(
            success=True,
            participant={
                "id": str(participant.id),
                "email": participant.email,
                "username": participant.username,
                "name": participant.name,
                "email_verified": participant.email_verified,
            },
        )
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


# =============================================================================
# Participant Registration
# =============================================================================


@router.post(
    "/register",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit("auth:register", (5, 60), (20, 3600)))],
)
async def register(
    request: Request,
    data: RegisterRequest,
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """
    Register a new participant for an event.

    Flow:
    1. Validate input
    2. Check event exists and registration is open
    3. Create participant with unverified email
    4. Send verification email
    5. Return success (user must verify email to continue)
    """
    # Verify captcha (no-op unless Turnstile is configured)
    await verify_turnstile(data.turnstile_token, get_client_ip(request))

    # Validate username
    if not is_valid_username(data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username format",
        )
    
    # Find event
    result = await db.execute(
        select(Event).where(Event.slug == data.event_slug.lower())
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    
    # Check registration is open
    if event.status != EventStatus.REGISTRATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration is not open for this event",
        )
    
    if event.registration_end and datetime.now(timezone.utc) > event.registration_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration has ended",
        )
    
    # Check for existing participant
    result = await db.execute(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.email == data.email.lower(),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered for this event",
        )
    
    result = await db.execute(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.username == data.username.lower(),
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )
    
    # Create participant
    verification_token = generate_verification_token()
    
    participant = Participant(
        event_id=event.id,
        email=data.email.lower(),
        username=data.username.lower(),
        password_hash=hash_password(data.password),
        name=data.name,
        email_verification_token=verification_token,
        email_verification_sent_at=datetime.now(timezone.utc),
        registration_ip=get_client_ip(request),
        source="registration",
    )
    
    db.add(participant)
    await db.flush()
    
    # Log registration
    await _log_audit(
        db,
        action="account.register",
        participant_id=participant.id,
        ip_address=get_client_ip(request),
        metadata={"event_id": str(event.id)},
    )
    
    # Send verification email (async via queue in production)
    verification_url = f"{settings.app_url}/verify?token={verification_token}"
    
    await _send_verification_email(
        db, redis, participant, event, verification_url
    )
    
    return AuthResponse(
        success=True,
        message="Registration successful. Please check your email to verify your account.",
        participant={
            "id": str(participant.id),
            "email": participant.email,
            "username": participant.username,
            "email_verified": False,
        },
    )


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(
    request: Request,
    response: Response,
    data: VerifyEmailRequest,
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """
    Verify participant email address.
    
    On success:
    1. Mark email as verified
    2. Provision user to CTFd (if configured)
    3. Create session and log user in
    """
    # Find participant by token
    result = await db.execute(
        select(Participant).where(
            Participant.email_verification_token == data.token,
            Participant.email_verified == False,
        )
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    
    # Check token age (24 hours)
    if participant.email_verification_sent_at:
        token_age = datetime.now(timezone.utc) - participant.email_verification_sent_at
        if token_age > timedelta(hours=24):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired. Please request a new one.",
            )
    
    # Mark as verified
    participant.email_verified = True
    participant.email_verified_at = datetime.now(timezone.utc)
    participant.email_verification_token = None
    
    await db.flush()
    
    # Fetch event info for the response
    event_result = await db.execute(
        select(Event).where(Event.id == participant.event_id)
    )
    event = event_result.scalar_one_or_none()
    
    # Log verification
    await _log_audit(
        db,
        action="account.verify_email",
        participant_id=participant.id,
        ip_address=get_client_ip(request),
    )

    # Send welcome email now that the account is verified
    if event:
        await _send_welcome_email(db, redis, participant, event)

    # TODO: Provision to CTFd if configured
    # This should be done in background task
    
    # Create session
    session_id = await create_session(
        db,
        participant_id=participant.id,
        ip_address=get_client_ip(request),
        user_agent=get_user_agent(request),
    )
    
    # Set cookie
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=settings.session_cookie_httponly,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_lifetime_hours * 3600,
    )
    
    # Build event info for response
    event_info = None
    if event:
        event_settings = event.settings or {}
        event_info = {
            "id": str(event.id),
            "name": event.name,
            "slug": event.slug,
            "discord_url": event_settings.get("discord_url"),
            "event_url": event_settings.get("site_url") or event.ctfd_url,
        }
    
    return AuthResponse(
        success=True,
        message="Email verified successfully",
        participant={
            "id": str(participant.id),
            "email": participant.email,
            "username": participant.username,
            "name": participant.name,
            "email_verified": True,
        },
        event=event_info,
    )


@router.post(
    "/resend-verification",
    response_model=BaseResponse,
    dependencies=[Depends(rate_limit("auth:resend-verification", (3, 60), (10, 3600)))],
)
async def resend_verification(
    request: Request,
    data: ResendVerificationRequest,
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """Resend verification email."""
    # Find event
    result = await db.execute(
        select(Event).where(Event.slug == data.event_slug.lower())
    )
    event = result.scalar_one_or_none()
    
    if not event:
        # Don't reveal if event exists
        return BaseResponse(
            success=True,
            message="If the email is registered, a verification email has been sent.",
        )
    
    # Find participant
    result = await db.execute(
        select(Participant).where(
            Participant.event_id == event.id,
            Participant.email == data.email.lower(),
        )
    )
    participant = result.scalar_one_or_none()
    
    if not participant or participant.email_verified:
        # Don't reveal account status
        return BaseResponse(
            success=True,
            message="If the email is registered, a verification email has been sent.",
        )
    
    # Rate limit: max 1 email per 5 minutes
    if participant.email_verification_sent_at:
        time_since_last = datetime.now(timezone.utc) - participant.email_verification_sent_at
        if time_since_last < timedelta(minutes=5):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another verification email",
            )
    
    # Generate new token
    verification_token = generate_verification_token()
    participant.email_verification_token = verification_token
    participant.email_verification_sent_at = datetime.now(timezone.utc)
    # Send email
    verification_url = f"{settings.app_url}/verify?token={verification_token}"
    await _send_verification_email(db, redis, participant, event, verification_url)
    
    return BaseResponse(
        success=True,
        message="If the email is registered, a verification email has been sent.",
    )


# =============================================================================
# Helper Functions
# =============================================================================


async def _log_audit(
    db: AsyncSession,
    action: str,
    user_id=None,
    participant_id=None,
    ip_address=None,
    metadata=None,
):
    """Log an audit event."""
    log = AuditLog(
        action=action,
        user_id=user_id,
        participant_id=participant_id,
        actor_type="user" if user_id else ("participant" if participant_id else "system"),
        ip_address=ip_address,
        extra_data=metadata or {},
    )
    db.add(log)
    await db.flush()


async def _send_verification_email(
    db: AsyncSession,
    redis,
    participant: Participant,
    event: Event,
    verification_url: str,
):
    """Send verification email to participant."""
    from app.models import EmailProvider
    
    # Get active providers
    result = await db.execute(
        select(EmailProvider).where(
            EmailProvider.is_active == True
        ).order_by(EmailProvider.priority)
    )
    providers = result.scalars().all()
    
    if not providers:
        # Log warning but don't fail registration
        print("Warning: No email providers configured")
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
    result = await orchestrator.send(message, provider_configs)
    
    # Log email
    email_log = EmailLog(
        recipient_email=participant.email,
        participant_id=participant.id,
        provider_id=result.provider_id,
        provider_name=result.provider_name,
        subject=subject,
        template_slug="verification",
        status=EmailStatus.SENT if result.success else EmailStatus.FAILED,
        error_message=result.error,
        attempts=result.attempts,
        sent_at=datetime.now(timezone.utc) if result.success else None,
    )
    db.add(email_log)
    await db.flush()


# =============================================================================
# Discord OAuth — participant identity verification (used by the registration popup)
# =============================================================================


@router.get(
    "/discord/authorize",
    dependencies=[Depends(rate_limit("auth:discord-authorize", (15, 60), (100, 3600)))],
)
async def discord_authorize(origin: str):
    """
    Begin Discord OAuth for registration identity verification.

    ``origin`` is the lander origin that opened the popup; it is validated against an
    allowlist and signed into the OAuth ``state`` so the callback can postMessage back to it.
    """
    if not settings.discord_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Discord verification is not configured",
        )
    if not discord_oauth.popup_origin_allowed(origin):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid origin")
    state = discord_oauth.make_state(origin)
    return RedirectResponse(discord_oauth.build_authorize_url(state), status_code=302)


@router.get("/discord/callback")
async def discord_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """Discord redirects here; postMessage a verify token (or an error) back to the popup opener."""
    origin = discord_oauth.read_state(state) if state else None
    if not origin or not discord_oauth.popup_origin_allowed(origin):
        return HTMLResponse(
            discord_oauth.result_html("*", {"type": "discord_error", "error": "invalid_state"}),
            status_code=400,
        )
    if error or not code:
        return HTMLResponse(
            discord_oauth.result_html(origin, {"type": "discord_error", "error": error or "no_code"})
        )

    user = await discord_oauth.exchange_code(code)
    if not user or not user.get("id"):
        return HTMLResponse(
            discord_oauth.result_html(origin, {"type": "discord_error", "error": "exchange_failed"})
        )

    age = discord_oauth.account_age_days(user["id"])
    if age is None or age < settings.discord_min_account_age_days:
        return HTMLResponse(
            discord_oauth.result_html(
                origin,
                {
                    "type": "discord_error",
                    "error": "account_too_new",
                    "min_days": settings.discord_min_account_age_days,
                },
            )
        )

    token = discord_oauth.issue_verify_token(
        user["id"], user.get("username", ""), user.get("global_name")
    )
    return HTMLResponse(
        discord_oauth.result_html(
            origin,
            {
                "type": "discord_verified",
                "token": token,
                "username": user.get("username", ""),
                "global_name": user.get("global_name") or user.get("username", ""),
            },
        )
    )


async def _send_welcome_email(
    db: AsyncSession,
    redis,
    participant: Participant,
    event: Event,
):
    """Send welcome email to participant after email verification."""
    from app.models import EmailProvider

    # Get active providers
    result = await db.execute(
        select(EmailProvider).where(
            EmailProvider.is_active == True
        ).order_by(EmailProvider.priority)
    )
    providers = result.scalars().all()

    if not providers:
        # Log warning but don't fail verification
        print("Warning: No email providers configured")
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

    event_settings = event.settings or {}
    template = DEFAULT_TEMPLATES["welcome"]
    variables = {
        "event_name": event.name,
        "name": participant.name,
        "username": participant.username,
        "ctfd_url": event_settings.get("site_url") or event.ctfd_url or settings.app_url,
        "discord_url": event_settings.get("discord_url"),
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
        template_slug="welcome",
    )

    # Send via orchestrator
    orchestrator = EmailOrchestrator(redis)
    result = await orchestrator.send(message, provider_configs)

    # Log email
    email_log = EmailLog(
        recipient_email=participant.email,
        participant_id=participant.id,
        provider_id=result.provider_id,
        provider_name=result.provider_name,
        subject=subject,
        template_slug="welcome",
        status=EmailStatus.SENT if result.success else EmailStatus.FAILED,
        error_message=result.error,
        attempts=result.attempts,
        sent_at=datetime.now(timezone.utc) if result.success else None,
    )
    db.add(email_log)
    await db.flush()


async def _send_password_reset_email(
    db: AsyncSession,
    redis,
    *,
    to_email: str,
    name: str,
    reset_url: str,
    event_name: Optional[str] = None,
    participant_id=None,
):
    """Send a password reset email via the provider pool. No-op if none configured."""
    from app.models import EmailProvider
    from app.services.email.templates import DEFAULT_TEMPLATES

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

    template = DEFAULT_TEMPLATES["password_reset"]
    variables = {
        "name": name,
        "reset_url": reset_url,
        "event_name": event_name,
    }

    body_html, body_text = render_email(
        template["body_html"],
        variables,
        template["body_text"],
    )
    subject = render_subject(template["subject"], variables)

    message = EmailMessage(
        to=to_email,
        subject=subject,
        body_html=body_html,
        body_text=body_text,
        participant_id=participant_id,
        template_slug="password_reset",
    )

    orchestrator = EmailOrchestrator(redis)
    result = await orchestrator.send(message, provider_configs)

    email_log = EmailLog(
        recipient_email=to_email,
        participant_id=participant_id,
        provider_id=result.provider_id,
        provider_name=result.provider_name,
        subject=subject,
        template_slug="password_reset",
        status=EmailStatus.SENT if result.success else EmailStatus.FAILED,
        error_message=result.error,
        attempts=result.attempts,
        sent_at=datetime.now(timezone.utc) if result.success else None,
    )
    db.add(email_log)
    await db.flush()


class ForgotPasswordRequest(BaseModel):
    email: str
    event_slug: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


@router.post(
    "/forgot-password",
    response_model=BaseResponse,
    dependencies=[Depends(rate_limit("auth:forgot-password", (3, 60), (10, 3600)))],
)
async def forgot_password(
    data: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """
    Request password reset for participant or admin.
    Always returns success to prevent email enumeration.
    """
    import secrets
    
    email = data.email.lower().strip()
    
    # Check if it's an admin user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if user:
        # Generate reset token for admin
        token = secrets.token_urlsafe(32)
        await redis.setex(f"password_reset:admin:{token}", 3600, str(user.id))
        
        # Build reset URL
        reset_url = f"{settings.app_url}/reset-password?token={token}"
        
        # Send password reset email via the provider pool
        await _send_password_reset_email(
            db,
            redis,
            to_email=user.email,
            name=user.username,
            reset_url=reset_url,
        )
        
        # Log the request
        audit_log = AuditLog(
            action="auth.password_reset_request",
            user_id=user.id,
            actor_type="user",
            resource_type="user",
            resource_id=user.id,
            ip_address=get_client_ip(request),
            extra_data={"email": email},
        )
        db.add(audit_log)
        await db.flush()

        return BaseResponse(success=True, message="If an account exists, a reset link has been sent")
    
    # Check if it's a participant
    if data.event_slug:
        result = await db.execute(select(Event).where(Event.slug == data.event_slug))
        event = result.scalar_one_or_none()
        
        if event:
            result = await db.execute(
                select(Participant).where(
                    Participant.event_id == event.id,
                    Participant.email == email,
                )
            )
            participant = result.scalar_one_or_none()
            
            if participant:
                token = secrets.token_urlsafe(32)
                await redis.setex(
                    f"password_reset:participant:{token}", 
                    3600, 
                    f"{participant.id}:{event.id}"
                )
                
                reset_url = f"{settings.app_url}/reset-password?token={token}"

                await _send_password_reset_email(
                    db,
                    redis,
                    to_email=participant.email,
                    name=participant.name or participant.username,
                    reset_url=reset_url,
                    event_name=event.name,
                    participant_id=participant.id,
                )
    
    return BaseResponse(success=True, message="If an account exists, a reset link has been sent")


@router.post("/reset-password", response_model=BaseResponse)
async def reset_password(
    data: ResetPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
):
    """Reset password using token."""
    token = data.token.strip()
    
    # Check admin reset
    admin_data = await redis.get(f"password_reset:admin:{token}")
    if admin_data:
        user_id = admin_data.decode() if isinstance(admin_data, bytes) else admin_data
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if user:
            user.password_hash = hash_password(data.password)
            await redis.delete(f"password_reset:admin:{token}")
            await db.flush()
            
            audit_log = AuditLog(
                action="auth.password_reset",
                user_id=user.id,
                actor_type="user",
                resource_type="user",
                resource_id=user.id,
                ip_address=get_client_ip(request),
            )
            db.add(audit_log)
            await db.flush()
            
            return BaseResponse(success=True, message="Password reset successfully")
    
    # Check participant reset
    participant_data = await redis.get(f"password_reset:participant:{token}")
    if participant_data:
        data_str = participant_data.decode() if isinstance(participant_data, bytes) else participant_data
        participant_id, event_id = data_str.split(":")
        
        result = await db.execute(
            select(Participant).where(Participant.id == participant_id)
        )
        participant = result.scalar_one_or_none()
        
        if participant:
            participant.password_hash = hash_password(data.password)
            await redis.delete(f"password_reset:participant:{token}")
            await db.flush()
            
            return BaseResponse(success=True, message="Password reset successfully")
    
    raise HTTPException(status_code=400, detail="Invalid or expired reset token")