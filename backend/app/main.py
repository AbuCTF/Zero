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
    print(f"Starting {settings.app_name}...")
    
    await init_db()
    
    app.state.redis = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    
    from app.bootstrap import bootstrap_application
    await bootstrap_application()
    
    print(f"{settings.app_name} started successfully")
    
    yield
    
    print(f"Shutting down {settings.app_name}...")
    
    await app.state.redis.close()
    
    await close_db()
    
    print(f"{settings.app_name} shut down")


app = FastAPI(
    title=settings.app_name,
    description="Universal Event Registration & Prize Distribution Platform",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
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


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "app": settings.app_name,
        "docs": "/docs" if settings.debug else None,
    }


from app.api import admin, auth, certificates, events, participants, prizes

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(
    participants.router, prefix="/api/participants", tags=["Participants"]
)
app.include_router(prizes.router, prefix="/api/prizes", tags=["Prizes"])
app.include_router(
    certificates.router, prefix="/api/certificates", tags=["Certificates"]
)

app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


upload_path = Path(settings.upload_dir)
upload_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(upload_path)), name="uploads")
