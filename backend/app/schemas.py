"""
Pydantic Schemas for API Request/Response

Defines all data transfer objects used in the API.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# =============================================================================
# Base Schemas
# =============================================================================


class BaseResponse(BaseModel):
    """Base response schema."""
    success: bool = True
    message: Optional[str] = None


class PaginatedResponse(BaseResponse):
    """Paginated response schema."""
    total: int
    page: int
    per_page: int
    pages: int


class ErrorResponse(BaseModel):
    """Error response schema."""
    success: bool = False
    error: str
    detail: Optional[Dict[str, Any]] = None


# =============================================================================
# Authentication Schemas
# =============================================================================


class LoginRequest(BaseModel):
    """Login request for both users and participants."""
    email: EmailStr
    password: str = Field(..., min_length=1)
    turnstile_token: Optional[str] = None


class RegisterRequest(BaseModel):
    """Participant registration request."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=255)
    event_slug: str = Field(..., min_length=1)
    turnstile_token: Optional[str] = None
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        import re
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_-]*$', v):
            raise ValueError("Username must start with a letter and contain only letters, numbers, underscores, and hyphens")
        return v


class VerifyEmailRequest(BaseModel):
    """Email verification request."""
    token: str


class ResendVerificationRequest(BaseModel):
    """Resend verification email request."""
    email: EmailStr
    event_slug: str


class PasswordResetRequest(BaseModel):
    """Password reset request."""
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Password reset confirmation."""
    token: str
    password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseResponse):
    """Authentication response."""
    user: Optional[Dict[str, Any]] = None
    participant: Optional[Dict[str, Any]] = None
    event: Optional[Dict[str, Any]] = None  # Event info for post-verification


# =============================================================================
# User Schemas
# =============================================================================


class UserCreate(BaseModel):
    """Create user request (admin only)."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = None
    role: str = "organizer"


class UserUpdate(BaseModel):
    """Update user request."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """User response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: str
    username: str
    name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]


# =============================================================================
# Event Schemas
# =============================================================================


class EventCreate(BaseModel):
    """Create event request."""
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    registration_start: Optional[datetime] = None
    registration_end: Optional[datetime] = None
    registration_open: Optional[datetime] = None  # Alias for registration_start
    registration_close: Optional[datetime] = None  # Alias for registration_end
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None
    start_date: Optional[datetime] = None  # Alias for event_start
    end_date: Optional[datetime] = None  # Alias for event_end
    ctfd_url: Optional[str] = None
    ctfd_api_key: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    
    # Settings fields that frontend sends as top-level
    is_import_only: Optional[bool] = None
    team_mode: Optional[bool] = None
    max_participants: Optional[int] = None
    min_team_size: Optional[int] = None
    max_team_size: Optional[int] = None
    
    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        import re
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        return v
    
    def get_settings(self) -> Dict[str, Any]:
        """Build settings dict from top-level fields and settings dict."""
        s = self.settings.copy() if self.settings else {}
        if self.is_import_only is not None:
            s["is_import_only"] = self.is_import_only
        if self.team_mode is not None:
            s["team_mode"] = self.team_mode
        if self.max_participants is not None:
            s["max_participants"] = self.max_participants
        if self.min_team_size is not None:
            s["min_team_size"] = self.min_team_size
        if self.max_team_size is not None:
            s["max_team_size"] = self.max_team_size
        return s
    
    def get_registration_start(self) -> Optional[datetime]:
        """Get registration start from either field."""
        return self.registration_start or self.registration_open
    
    def get_registration_end(self) -> Optional[datetime]:
        """Get registration end from either field."""
        return self.registration_end or self.registration_close
    
    def get_event_start(self) -> Optional[datetime]:
        """Get event start from either field."""
        return self.event_start or self.start_date
    
    def get_event_end(self) -> Optional[datetime]:
        """Get event end from either field."""
        return self.event_end or self.end_date


class EventUpdate(BaseModel):
    """Update event request."""
    name: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    registration_start: Optional[datetime] = None
    registration_end: Optional[datetime] = None
    registration_open: Optional[datetime] = None   # Alias for registration_start
    registration_close: Optional[datetime] = None  # Alias for registration_end
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None
    status: Optional[str] = None
    ctfd_url: Optional[str] = None
    ctfd_api_key: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

    # Settings fields that frontend sends as top-level
    is_import_only: Optional[bool] = None
    team_mode: Optional[bool] = None
    max_participants: Optional[int] = None
    min_team_size: Optional[int] = None
    max_team_size: Optional[int] = None
    discord_url: Optional[str] = None
    site_url: Optional[str] = None

    def get_registration_start(self) -> Optional[datetime]:
        return self.registration_start or self.registration_open

    def get_registration_end(self) -> Optional[datetime]:
        return self.registration_end or self.registration_close


class EventResponse(BaseModel):
    """Event response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    slug: str
    description: Optional[str]
    status: str
    registration_start: Optional[datetime]
    registration_end: Optional[datetime]
    event_start: Optional[datetime]
    event_end: Optional[datetime]
    ctfd_url: Optional[str]
    ctfd_synced_at: Optional[datetime]
    settings: Dict[str, Any]
    created_at: datetime
    
    # Stats (populated separately)
    participant_count: Optional[int] = None
    verified_count: Optional[int] = None
    
    # Computed fields for frontend convenience
    is_import_only: Optional[bool] = None
    team_mode: Optional[bool] = None


class EventListResponse(PaginatedResponse):
    """Event list response."""
    events: List[EventResponse]


# =============================================================================
# Participant Schemas
# =============================================================================


class ParticipantCreate(BaseModel):
    """Create participant (for import)."""
    email: EmailStr
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ParticipantUpdate(BaseModel):
    """Update participant."""
    name: Optional[str] = None
    username: Optional[str] = None
    is_blocked: Optional[bool] = None
    final_rank: Optional[int] = None
    final_score: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ParticipantBulkRankUpdate(BaseModel):
    """Bulk update participant ranks."""
    participants: List[Dict[str, Any]]  # [{id: str, final_rank: int, final_score: int}]


class ParticipantResponse(BaseModel):
    """Participant response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    email: str
    username: str
    name: Optional[str]
    email_verified: bool
    email_verified_at: Optional[datetime]
    ctfd_provisioned: bool
    ctfd_user_id: Optional[int]
    final_rank: Optional[int]
    final_score: Optional[float]
    is_blocked: bool
    source: str
    created_at: datetime
    extra_data: Dict[str, Any] = {}


class ParticipantListResponse(PaginatedResponse):
    """Participant list response."""
    participants: List[ParticipantResponse]


class ParticipantImportRequest(BaseModel):
    """Bulk import participants request."""
    participants: List[ParticipantCreate]
    send_notification: bool = False
    generate_passwords: bool = True


class ParticipantImportResponse(BaseResponse):
    """Bulk import response."""
    imported: int
    updated: int = 0
    skipped: int
    errors: List[Dict[str, Any]]
    job_id: Optional[str] = None  # For background imports
    message: Optional[str] = None


# =============================================================================
# Email Provider Schemas
# =============================================================================


class EmailProviderCreate(BaseModel):
    """Create email provider."""
    name: str = Field(..., max_length=100)
    provider_type: str  # 'smtp', 'brevo', 'mailgun', 'aws_ses'
    config: Dict[str, Any]
    daily_limit: Optional[int] = None
    hourly_limit: Optional[int] = None
    minute_limit: Optional[int] = None
    second_limit: Optional[int] = None
    monthly_limit: Optional[int] = None
    priority: int = 10


class EmailProviderUpdate(BaseModel):
    """Update email provider."""
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    daily_limit: Optional[int] = None
    hourly_limit: Optional[int] = None
    minute_limit: Optional[int] = None
    second_limit: Optional[int] = None
    monthly_limit: Optional[int] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class EmailProviderResponse(BaseModel):
    """Email provider response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    provider_type: str
    daily_limit: Optional[int]
    hourly_limit: Optional[int]
    minute_limit: Optional[int]
    second_limit: Optional[int]
    monthly_limit: Optional[int]
    priority: int
    is_active: bool
    is_healthy: bool
    last_error: Optional[str]
    last_error_at: Optional[datetime]
    created_at: datetime
    
    # Usage stats (populated from Redis)
    daily_used: Optional[int] = None
    hourly_used: Optional[int] = None
    available: Optional[bool] = None


class EmailProviderTestRequest(BaseModel):
    """Test email provider request."""
    recipient_email: EmailStr


class EmailProviderTestResponse(BaseResponse):
    """Test email provider response."""
    sent: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


# =============================================================================
# Email Template Schemas
# =============================================================================


class EmailTemplateCreate(BaseModel):
    """Create email template."""
    event_id: Optional[UUID] = None
    slug: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    subject: str = Field(..., max_length=500)
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = []


class EmailTemplateUpdate(BaseModel):
    """Update email template."""
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None


class EmailTemplateResponse(BaseModel):
    """Email template response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    event_id: Optional[UUID]
    slug: str
    name: str
    description: Optional[str]
    subject: str
    body_html: str
    body_text: Optional[str]
    variables: List[str]
    is_active: bool
    created_at: datetime


# =============================================================================
# Voucher Schemas
# =============================================================================


class VoucherPoolCreate(BaseModel):
    """Create voucher pool."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    platform: Optional[str] = None


class VoucherPoolResponse(BaseModel):
    """Voucher pool response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    event_id: UUID
    name: str
    description: Optional[str]
    platform: Optional[str]
    total_count: int
    claimed_count: int
    created_at: datetime


class VoucherUploadRequest(BaseModel):
    """Bulk voucher upload request."""
    codes: List[str]


class VoucherResponse(BaseModel):
    """Voucher response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    code: str
    status: str
    claimed_by: Optional[UUID]
    claimed_at: Optional[datetime]


# =============================================================================
# Prize Schemas
# =============================================================================


class PrizeRuleCreate(BaseModel):
    """Create prize rule."""
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    rank_from: int = Field(..., ge=1)
    rank_to: int = Field(..., ge=1)
    voucher_pool_id: Optional[UUID] = None
    certificate_template_id: Optional[UUID] = None
    custom_prize: Optional[Dict[str, Any]] = None
    priority: int = 10


class PrizeRuleResponse(BaseModel):
    """Prize rule response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    event_id: UUID
    name: str
    description: Optional[str]
    rank_from: int
    rank_to: int
    voucher_pool_id: Optional[UUID]
    certificate_template_id: Optional[UUID]
    custom_prize: Optional[Dict[str, Any]]
    priority: int
    is_active: bool


class PrizeResponse(BaseModel):
    """Prize response (for participants)."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    prize_type: str
    prize_data: Dict[str, Any]
    status: str
    claimed_at: Optional[datetime]
    created_at: datetime


class PrizeClaimRequest(BaseModel):
    """Prize claim request."""
    pass  # No body needed, just POST to claim


# =============================================================================
# Certificate Schemas
# =============================================================================


class CertificateTemplateCreate(BaseModel):
    """Create certificate template."""
    event_id: UUID
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    background_image: Optional[str] = None  # URL or base64 of background image
    width: int = 1920
    height: int = 1080
    text_zones: List[Dict[str, Any]] = []
    qr_zone: Optional[Dict[str, Any]] = None
    output_format: str = "pdf"
    rank_from: Optional[int] = None
    rank_to: Optional[int] = None
    is_default: bool = False


class CertificateTemplateUpdate(BaseModel):
    """Update certificate template."""
    name: Optional[str] = None
    description: Optional[str] = None
    background_image: Optional[str] = None  # URL or base64 of background image
    width: Optional[int] = None
    height: Optional[int] = None
    text_zones: Optional[List[Dict[str, Any]]] = None
    qr_zone: Optional[Dict[str, Any]] = None
    output_format: Optional[str] = None
    rank_from: Optional[int] = None
    rank_to: Optional[int] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


class CertificateTemplateResponse(BaseModel):
    """Certificate template response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    event_id: UUID
    name: str
    description: Optional[str]
    template_file: Optional[str] = None
    background_image: Optional[str] = None  # Computed URL for frontend preview
    width: int
    height: int
    text_zones: List[Dict[str, Any]]
    qr_zone: Optional[Dict[str, Any]]
    output_format: str
    rank_from: Optional[int]
    rank_to: Optional[int]
    is_active: bool
    is_default: Optional[bool] = False
    created_at: datetime


class CertificateCustomizeRequest(BaseModel):
    """Certificate customization request."""
    display_name: str = Field(..., min_length=1, max_length=255)


class CertificatePreviewRequest(BaseModel):
    """Certificate preview request."""
    display_name: str = Field(..., min_length=1, max_length=255)


class CertificateResponse(BaseModel):
    """Certificate response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    display_name: str
    team_name: Optional[str]
    rank: Optional[int]
    verification_code: str
    generated_at: Optional[datetime]
    download_count: int


class CertificateVerifyResponse(BaseModel):
    """Certificate verification response (public)."""
    valid: bool
    participant_name: Optional[str] = None
    team_name: Optional[str] = None
    rank: Optional[int] = None
    event_name: Optional[str] = None
    issued_at: Optional[datetime] = None


# =============================================================================
# Campaign Schemas
# =============================================================================


class CampaignCreate(BaseModel):
    """Create email campaign."""
    name: str = Field(..., max_length=255)
    subject: str = Field(..., max_length=500)
    body_html: str
    body_text: Optional[str] = None
    target_group: str  # 'all', 'verified', 'top_n', 'rank_range', 'custom'
    target_config: Dict[str, Any] = {}
    scheduled_for: Optional[datetime] = None


class CampaignResponse(BaseModel):
    """Campaign response."""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    event_id: UUID
    name: str
    subject: str
    target_group: str
    target_config: Dict[str, Any]
    status: str
    scheduled_for: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_recipients: int
    sent_count: int
    failed_count: int
    created_at: datetime


# =============================================================================
# Analytics Schemas
# =============================================================================


class DashboardStats(BaseModel):
    """Dashboard statistics."""
    total_events: int
    active_events: int
    total_participants: int
    verified_participants: int
    total_emails_sent: int
    emails_sent_today: int
    total_certificates: int
    certificates_downloaded: int
    total_prizes: int
    prizes_claimed: int
    
    # Provider stats
    providers_active: int
    providers_total: int
    daily_email_capacity: int
    daily_emails_used: int


class EventStats(BaseModel):
    """Event-specific statistics."""
    participant_count: int
    verified_count: int
    ctfd_provisioned_count: int
    team_count: int
    emails_sent: int
    certificates_generated: int
    certificates_downloaded: int
    prizes_assigned: int
    prizes_claimed: int
    vouchers_total: int
    vouchers_claimed: int
