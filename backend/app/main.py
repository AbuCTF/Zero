"""
ZeroPool API - Main Application Entry Point
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from redis import asyncio as aioredis

from app.config import get_settings
from app.database import close_db, init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    print(f"Starting {settings.app_name}...")
    
    # Initialize database
    await init_db()
    
    # Initialize Redis
    app.state.redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    
    # Bootstrap admin user and default templates on first run
    from app.bootstrap import bootstrap_application
    await bootstrap_application()
    
    print(f"{settings.app_name} started successfully")
    
    yield
    
    # Shutdown
    print(f"Shutting down {settings.app_name}...")
    
    # Close Redis
    await app.state.redis.close()
    
    # Close database
    await close_db()
    
    print(f"{settings.app_name} shut down")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Universal Event Registration & Prize Distribution Platform",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    # Log the error
    print(f"Unhandled error: {exc}")
    
    if settings.debug:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(exc),
                "type": type(exc).__name__,
            },
        )
    else:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "An internal error occurred",
            },
        )


# =============================================================================
# Health Check
# =============================================================================


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
    }


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "docs": "/docs" if settings.debug else None,
    }


# =============================================================================
# Include Routers
# =============================================================================

from app.api import admin, auth, certificates, events, participants, prizes

# Public routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(
    participants.router, prefix="/api/participants", tags=["Participants"]
)
app.include_router(prizes.router, prefix="/api/prizes", tags=["Prizes"])
app.include_router(
    certificates.router, prefix="/api/certificates", tags=["Certificates"]
)

# Admin routes
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


# =============================================================================
# Static Files
# =============================================================================

# Mount uploads directory for serving certificate templates and other uploads
upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")
