#!/usr/bin/env python3
"""
ZeroPool CLI - Admin management commands

Usage:
    docker exec -it zero-api-1 python cli.py add-admin email@example.com "Admin Name" password123
    docker exec -it zero-api-1 python cli.py list-admins
    docker exec -it zero-api-1 python cli.py delete-admin email@example.com
"""

import asyncio
import sys
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import User, UserRole
from app.utils.security import hash_password

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def add_admin(email: str, name: str, password: str):
    """Add a new admin user."""
    async with async_session() as db:
        # Check if exists
        result = await db.execute(select(User).where(User.email == email.lower()))
        existing = result.scalar_one_or_none()
        
        if existing:
            print(f"❌ User with email {email} already exists")
            return False
        
        user = User(
            id=uuid4(),
            email=email.lower(),
            password_hash=hash_password(password),
            name=name,
            role=UserRole.admin,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        
        print(f"✅ Admin '{name}' ({email}) created successfully")
        return True


async def list_admins():
    """List all admin users."""
    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.role == UserRole.admin).order_by(User.created_at)
        )
        users = result.scalars().all()
        
        if not users:
            print("No admins found")
            return
        
        print(f"\n{'Email':<35} {'Name':<25} {'Active':<8} {'Created'}")
        print("-" * 90)
        for u in users:
            print(f"{u.email:<35} {u.name or '-':<25} {'Yes' if u.is_active else 'No':<8} {u.created_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"\nTotal: {len(users)} admin(s)")


async def delete_admin(email: str):
    """Delete an admin user."""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ User with email {email} not found")
            return False
        
        # Count remaining admins
        count_result = await db.execute(
            select(User).where(User.role == UserRole.admin, User.is_active == True)
        )
        admin_count = len(count_result.scalars().all())
        
        if admin_count <= 1:
            print("❌ Cannot delete the last admin")
            return False
        
        await db.delete(user)
        await db.commit()
        
        print(f"✅ Admin '{user.name}' ({email}) deleted")
        return True


async def reset_password(email: str, new_password: str):
    """Reset an admin's password."""
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == email.lower()))
        user = result.scalar_one_or_none()
        
        if not user:
            print(f"❌ User with email {email} not found")
            return False
        
        user.password_hash = hash_password(new_password)
        await db.commit()
        
        print(f"✅ Password reset for '{user.name}' ({email})")
        return True


def print_usage():
    print("""
ZeroPool CLI - Admin Management

Commands:
    add-admin <email> <name> <password>  - Create a new admin
    list-admins                          - List all admins
    delete-admin <email>                 - Delete an admin
    reset-password <email> <password>    - Reset admin password

Examples:
    python cli.py add-admin admin@h7tex.com "John Doe" secretpass123
    python cli.py list-admins
    python cli.py delete-admin old@admin.com
    python cli.py reset-password admin@h7tex.com newpassword456
""")


async def main():
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1]
    
    if command == "add-admin":
        if len(sys.argv) < 5:
            print("Usage: python cli.py add-admin <email> <name> <password>")
            return
        await add_admin(sys.argv[2], sys.argv[3], sys.argv[4])
    
    elif command == "list-admins":
        await list_admins()
    
    elif command == "delete-admin":
        if len(sys.argv) < 3:
            print("Usage: python cli.py delete-admin <email>")
            return
        await delete_admin(sys.argv[2])
    
    elif command == "reset-password":
        if len(sys.argv) < 4:
            print("Usage: python cli.py reset-password <email> <password>")
            return
        await reset_password(sys.argv[2], sys.argv[3])
    
    else:
        print(f"Unknown command: {command}")
        print_usage()


if __name__ == "__main__":
    asyncio.run(main())
