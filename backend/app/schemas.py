"""pydantic schemas for api request/response."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class BaseResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None


class PaginatedResponse(BaseResponse):
    total: int
    page: int
    per_page: int
    pages: int


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[Dict[str, Any]] = None


class LoginRequest(BaseModel):
    # login for both users and participants
    email: EmailStr
    password: str = Field(..., min_length=1)
    turnstile_token: Optional[str] = None


class RegisterRequest(BaseModel):
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
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr
    event_slug: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str
    password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseResponse):
    user: Optional[Dict[str, Any]] = None
    participant: Optional[Dict[str, Any]] = None
    event: Optional[Dict[str, Any]] = None  # event info for post-verification


class UserCreate(BaseModel):
    # admin only
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    name: Optional[str] = None
    role: str = "organizer"


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    name: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    username: str
    name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]


class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    registration_start: Optional[datetime] = None
    registration_end: Optional[datetime] = None
    registration_open: Optional[datetime] = None  # alias for registration_start
    registration_close: Optional[datetime] = None  # alias for registration_end
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None
    start_date: Optional[datetime] = None  # alias for event_start
    end_date: Optional[datetime] = None  # alias for event_end
    ctfd_url: Optional[str] = None
    ctfd_api_key: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

    # settings fields the frontend sends as top-level
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
        return self.registration_start or self.registration_open

    def get_registration_end(self) -> Optional[datetime]:
        return self.registration_end or self.registration_close

    def get_event_start(self) -> Optional[datetime]:
        return self.event_start or self.start_date

    def get_event_end(self) -> Optional[datetime]:
        return self.event_end or self.end_date


class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    slug: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    registration_start: Optional[datetime] = None
    registration_end: Optional[datetime] = None
    registration_open: Optional[datetime] = None   # alias for registration_start
    registration_close: Optional[datetime] = None  # alias for registration_end
    event_start: Optional[datetime] = None
    event_end: Optional[datetime] = None
    start_date: Optional[datetime] = None  # alias for event_start
    end_date: Optional[datetime] = None    # alias for event_end
    status: Optional[str] = None
    ctfd_url: Optional[str] = None
    ctfd_api_key: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None

    # settings fields the frontend sends as top-level
    is_import_only: Optional[bool] = None
    team_mode: Optional[bool] = None
    max_participants: Optional[int] = None
    min_team_size: Optional[int] = None
    max_team_size: Optional[int] = None
    discord_url: Optional[str] = None
    site_url: Optional[str] = None

    @field_validator(
        "registration_start",
        "registration_end",
        "registration_open",
        "registration_close",
        "event_start",
        "event_end",
        "start_date",
        "end_date",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, v):
        # frontend sends empty datetime-local inputs as ""; treat as none
        return None if v == "" else v

    def get_registration_start(self) -> Optional[datetime]:
        return self.registration_start or self.registration_open

    def get_registration_end(self) -> Optional[datetime]:
        return self.registration_end or self.registration_close

    def get_event_start(self) -> Optional[datetime]:
        return self.event_start or self.start_date

    def get_event_end(self) -> Optional[datetime]:
        return self.event_end or self.end_date


class EventResponse(BaseModel):
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

    # populated separately
    participant_count: Optional[int] = None
    verified_count: Optional[int] = None
    with_results_count: Optional[int] = None

    # computed for frontend convenience
    is_import_only: Optional[bool] = None
    team_mode: Optional[bool] = None


class EventListResponse(PaginatedResponse):
    events: List[EventResponse]


class ParticipantCreate(BaseModel):
    # for import
    email: EmailStr
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ParticipantUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    is_blocked: Optional[bool] = None
    final_rank: Optional[int] = None
    final_score: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class ParticipantBulkRankUpdate(BaseModel):
    participants: List[Dict[str, Any]]  # [{id: str, final_rank: int, final_score: int}]


class ParticipantResponse(BaseModel):
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
    participants: List[ParticipantResponse]


class ParticipantImportRequest(BaseModel):
    participants: List[ParticipantCreate]
    send_notification: bool = False
    generate_passwords: bool = True


class ParticipantImportResponse(BaseResponse):
    imported: int
    updated: int = 0
    skipped: int
    errors: List[Dict[str, Any]]
    job_id: Optional[str] = None  # for background imports
    message: Optional[str] = None


class EmailProviderCreate(BaseModel):
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

    # populated from redis
    daily_used: Optional[int] = None
    hourly_used: Optional[int] = None
    available: Optional[bool] = None


class EmailProviderTestRequest(BaseModel):
    recipient_email: EmailStr


class EmailProviderTestResponse(BaseResponse):
    sent: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailTemplateCreate(BaseModel):
    event_id: Optional[UUID] = None
    slug: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    subject: str = Field(..., max_length=500)
    body_html: str
    body_text: Optional[str] = None
    variables: List[str] = []


class EmailTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    variables: Optional[List[str]] = None
    is_active: Optional[bool] = None


class EmailTemplateResponse(BaseModel):
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


class VoucherPoolCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    platform: Optional[str] = None


class VoucherPoolResponse(BaseModel):
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
    codes: List[str]


class VoucherResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    status: str
    claimed_by: Optional[UUID]
    claimed_at: Optional[datetime]


class PrizeRuleCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    rank_from: int = Field(..., ge=1)
    rank_to: int = Field(..., ge=1)
    voucher_pool_id: Optional[UUID] = None
    certificate_template_id: Optional[UUID] = None
    custom_prize: Optional[Dict[str, Any]] = None
    priority: int = 10


class PrizeRuleResponse(BaseModel):
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
    # for participants
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prize_type: str
    prize_data: Dict[str, Any]
    status: str
    claimed_at: Optional[datetime]
    created_at: datetime


class PrizeClaimRequest(BaseModel):
    pass  # no body needed, just post to claim


class CertificateTemplateCreate(BaseModel):
    event_id: Optional[UUID] = None  # none = global template (any event)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    background_image: Optional[str] = None  # url or base64 of background image
    width: int = 1920
    height: int = 1080
    text_zones: List[Dict[str, Any]] = []
    qr_zone: Optional[Dict[str, Any]] = None
    output_format: str = "pdf"
    rank_from: Optional[int] = None
    rank_to: Optional[int] = None
    is_default: bool = False


class CertificateTemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    background_image: Optional[str] = None  # url or base64 of background image
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
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: Optional[UUID] = None  # none = global template
    name: str
    description: Optional[str]
    template_file: Optional[str] = None
    background_image: Optional[str] = None  # computed url for frontend preview
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
    display_name: str = Field(..., min_length=1, max_length=255)


class CertificatePreviewRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    display_name: str
    team_name: Optional[str]
    rank: Optional[int]
    verification_code: str
    generated_at: Optional[datetime]
    download_count: int


class CertificateVerifyResponse(BaseModel):
    # public
    valid: bool
    participant_name: Optional[str] = None
    team_name: Optional[str] = None
    rank: Optional[int] = None
    event_name: Optional[str] = None
    issued_at: Optional[datetime] = None


class CampaignCreate(BaseModel):
    event_id: UUID
    template_id: UUID
    name: str = Field(..., max_length=255)
    recipient_filter: Dict[str, Any] = {}  # e.g. {"type": "verified"}
    scheduled_at: Optional[datetime] = None


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    name: str
    subject: str
    target_group: str
    target_config: Dict[str, Any]
    status: str
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    total_recipients: int
    sent_count: int
    failed_count: int
    created_at: datetime


class DashboardStats(BaseModel):
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

    providers_active: int
    providers_total: int
    daily_email_capacity: int
    daily_emails_used: int


class EventStats(BaseModel):
    participant_count: int
    verified_count: int
    with_results_count: int
    ctfd_provisioned_count: int
    team_count: int
    emails_sent: int
    certificates_generated: int
    certificates_downloaded: int
    prizes_assigned: int
    prizes_claimed: int
    vouchers_total: int
    vouchers_claimed: int
