"""
Services module.
"""

from app.services.certificates import CertificateData, CertificateGenerator, CertificateResult
from app.services.ctfd import CTFdClient, CTFdSyncService, CTFdUser, CTFdTeam
from app.services.email import (
    EmailOrchestrator,
    EmailMessage,
    SendResult,
    ProviderStatus,
    render_email,
    render_subject,
)

__all__ = [
    # CTFd
    "CTFdClient",
    "CTFdSyncService",
    "CTFdUser",
    "CTFdTeam",
    # Certificates
    "CertificateGenerator",
    "CertificateData",
    "CertificateResult",
    # Email
    "EmailOrchestrator",
    "EmailMessage",
    "SendResult",
    "ProviderStatus",
    "render_email",
    "render_subject",
]
