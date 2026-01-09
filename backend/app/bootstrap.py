"""
Application Bootstrap

First-run initialization:
- Create admin user
- Set up default email templates
- Initialize system settings
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session_context
from app.models import EmailTemplate, SystemSetting, User, UserRole
from app.services.email.templates import DEFAULT_TEMPLATES
from app.utils.security import hash_password

settings = get_settings()


async def bootstrap_application() -> None:
    """
    Bootstrap the application on first run.
    
    Creates:
    - Admin user (if not exists)
    - Default email templates (if not exist)
    - System settings
    """
    async with get_session_context() as db:
        await create_admin_user(db)
        await create_default_email_templates(db)
        await initialize_system_settings(db)


async def create_admin_user(db: AsyncSession) -> None:
    """Create the initial admin user if it doesn't exist."""
    # Check if any admin exists
    result = await db.execute(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )
    existing_admin = result.scalar_one_or_none()
    
    if existing_admin:
        return
    
    # Create admin user
    admin = User(
        email=settings.admin_email,
        username=settings.admin_username,
        password_hash=hash_password(settings.admin_password),
        name="Administrator",
        role=UserRole.ADMIN,
        is_active=True,
    )
    
    db.add(admin)
    await db.flush()
    
    print(f"Created admin user: {settings.admin_email}")


async def create_default_email_templates(db: AsyncSession) -> None:
    """Create default email templates if they don't exist."""
    for slug, template_data in DEFAULT_TEMPLATES.items():
        # Check if template exists
        result = await db.execute(
            select(EmailTemplate).where(
                EmailTemplate.slug == slug,
                EmailTemplate.event_id.is_(None),  # Global templates
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            continue
        
        # Create template
        template = EmailTemplate(
            slug=slug,
            name=template_data["name"],
            subject=template_data["subject"],
            body_html=template_data["body_html"].strip(),
            body_text=template_data.get("body_text", "").strip() or None,
            variables=template_data.get("variables", []),
            is_active=True,
        )
        
        db.add(template)
        print(f"Created email template: {slug}")
    
    await db.flush()


async def initialize_system_settings(db: AsyncSession) -> None:
    """Initialize default system settings."""
    default_settings = {
        "app_name": settings.app_name,
        "registration_enabled": True,
        "require_email_verification": True,
        "ctfd_auto_provision": True,
        "certificate_verification_url": f"{settings.app_url}/verify",
        "default_email_from_name": settings.email_from_name,
        "default_email_from_address": settings.email_from_address,
        "initialized_at": datetime.utcnow().isoformat(),
    }
    
    for key, value in default_settings.items():
        # Check if setting exists
        result = await db.execute(
            select(SystemSetting).where(SystemSetting.key == key)
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            continue
        
        # Create setting
        setting = SystemSetting(key=key, value=value)
        db.add(setting)
    
    await db.flush()
