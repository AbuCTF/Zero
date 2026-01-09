"""
Email services module.
"""

from app.services.email.orchestrator import (
    EmailMessage,
    EmailOrchestrator,
    ProviderHealth,
    ProviderStatus,
    SendResult,
    get_provider_instance,
)
from app.services.email.templates import (
    DEFAULT_TEMPLATES,
    EmailTemplateRenderer,
    render_email,
    render_subject,
)

__all__ = [
    # Orchestrator
    "EmailOrchestrator",
    "EmailMessage",
    "SendResult",
    "ProviderStatus",
    "ProviderHealth",
    "get_provider_instance",
    # Templates
    "EmailTemplateRenderer",
    "render_email",
    "render_subject",
    "DEFAULT_TEMPLATES",
]
