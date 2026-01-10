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
from app.utils.security import (
    generate_verification_token,
    hash_password,
    is_valid_email,
    is_valid_username,
    verify_password,
)

router = APIRouter()
settings = get_settings()


# =============================================================================
# Admin User Authentication
# =============================================================================


@router.post("/login", response_model=AuthResponse)
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: AsyncSession = Depends(get_session),
):
    """
    Login for admin users and participants.
    
    Determines account type by checking users table first, then participants.
    """
    # Try to find admin user
    result = await db.execute(
        select(User).where(User.email == data.email.lower())
    )
    user = result.scalar_one_or_none()
    
    if user:
        # Verify password
        if not verify_password(data.password, user.password_hash):
            # Log failed attempt
            await _log_audit(
                db,
                action="account.login_failed",
                user_id=user.id,
                ip_address=get_client_ip(request),
                metadata={"reason": "invalid_password"},
            )
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
        
        # Log success
        await _log_audit(
            db,
            action="account.login",
            user_id=user.id,
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


@router.post("/register", response_model=AuthResponse)
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
            "event_url": event_settings.get("event_url") or event.ctfd_url,
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


@router.post("/resend-verification", response_model=BaseResponse)
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
        metadata=metadata or {},
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


class ForgotPasswordRequest(BaseModel):
    email: str
    event_slug: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


@router.post("/forgot-password", response_model=BaseResponse)
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
        
        # TODO: Send password reset email to admin
        # For now, log the token (in production, send email)
        reset_url = f"{settings.app_url}/admin/reset-password?token={token}"
        
        # Log the request
        audit_log = AuditLog(
            action="auth.password_reset_request",
            user_id=user.id,
            actor_type="user",
            resource_type="user",
            resource_id=user.id,
            ip_address=get_client_ip(request),
            metadata={"email": email},
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
                
                reset_url = f"{settings.app_url}/events/{event.slug}/reset-password?token={token}"
                
                # TODO: Send password reset email to participant
    
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