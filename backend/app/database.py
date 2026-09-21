from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """fastapi dependency that provides a db session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """context manager for db sessions outside request context."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """create all tables if missing; for production use alembic migrations."""
    from sqlalchemy.exc import IntegrityError, ProgrammingError
    
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except (IntegrityError, ProgrammingError) as e:
            # ignore duplicate enum/type errors (race with multiple workers)
            if "already exists" in str(e):
                pass
            else:
                raise


async def close_db() -> None:
    await engine.dispose()
