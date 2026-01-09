"""
Authentication Dependencies

Handles session management and authentication for both
admin users and participants.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.models import Participant, Session, User, UserRole
from app.utils.security import generate_session_id

settings = get_settings()


async def get_redis(request: Request):
    """Get Redis connection from app state."""
    return request.app.state.redis


# =============================================================================
# Session Management
# =============================================================================


async def create_session(
    db: AsyncSession,
    user_id: Optional[UUID] = None,
    participant_id: Optional[UUID] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """
    Create a new session.
    
    Returns session ID to be stored in cookie.
    """
    session_id = generate_session_id()
    expires_at = datetime.utcnow() + timedelta(hours=settings.session_lifetime_hours)
    
    session = Session(
        id=session_id,
        user_id=user_id,
        participant_id=participant_id,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=expires_at,
    )
    
    db.add(session)
    await db.flush()
    
    return session_id


async def get_session_by_id(
    db: AsyncSession,
    session_id: str,
) -> Optional[Session]:
    """Get session by ID if not expired."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none()


async def delete_session(db: AsyncSession, session_id: str) -> None:
    """Delete a session."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.flush()


# =============================================================================
# Authentication Dependencies
# =============================================================================


async def get_current_session(
    db: AsyncSession = Depends(get_session),
    session_id: Optional[str] = Cookie(None, alias="zeropool_session"),
) -> Optional[Session]:
    """
    Get current session from cookie.
    
    Returns None if no valid session exists.
    """
    if not session_id:
        return None
    
    session = await get_session_by_id(db, session_id)
    
    if session:
        # Update last accessed time
        session.last_accessed_at = datetime.utcnow()
        await db.flush()
    
    return session


async def get_current_user(
    db: AsyncSession = Depends(get_session),
    session: Optional[Session] = Depends(get_current_session),
) -> Optional[User]:
    """
    Get current authenticated admin user.
    
    Returns None if not authenticated as user.
    """
    if not session or not session.user_id:
        return None
    
    result = await db.execute(
        select(User).where(
            User.id == session.user_id,
            User.is_active == True,
        )
    )
    return result.scalar_one_or_none()


async def get_current_participant(
    db: AsyncSession = Depends(get_session),
    session: Optional[Session] = Depends(get_current_session),
) -> Optional[Participant]:
    """
    Get current authenticated participant.
    
    Returns None if not authenticated as participant.
    """
    if not session or not session.participant_id:
        return None
    
    result = await db.execute(
        select(Participant).where(
            Participant.id == session.participant_id,
            Participant.is_blocked == False,
        )
    )
    return result.scalar_one_or_none()


async def require_user(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """
    Require authenticated admin user.
    
    Raises 401 if not authenticated.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


async def require_admin(
    user: User = Depends(require_user),
) -> User:
    """
    Require admin role.
    
    Raises 403 if not admin.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def require_organizer(
    user: User = Depends(require_user),
) -> User:
    """
    Require organizer or admin role.
    
    Raises 403 if not organizer or admin.
    """
    if user.role not in (UserRole.ADMIN, UserRole.ORGANIZER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organizer access required",
        )
    return user


async def require_participant(
    participant: Optional[Participant] = Depends(get_current_participant),
) -> Participant:
    """
    Require authenticated participant.
    
    Raises 401 if not authenticated as participant.
    """
    if not participant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Participant authentication required",
        )
    return participant


async def require_verified_participant(
    participant: Participant = Depends(require_participant),
) -> Participant:
    """
    Require verified participant.
    
    Raises 403 if email not verified.
    """
    if not participant.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    return participant


# =============================================================================
# Utility Functions
# =============================================================================


def get_client_ip(request: Request) -> Optional[str]:
    """Get client IP address from request."""
    # Check for proxy headers
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    if request.client:
        return request.client.host
    
    return None


def get_user_agent(request: Request) -> Optional[str]:
    """Get user agent from request."""
    return request.headers.get("User-Agent")
