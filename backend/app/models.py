"""zeropool database models (sqlalchemy 2.0)."""

import enum
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ORGANIZER = "organizer"
    PARTICIPANT = "participant"


class EventStatus(str, enum.Enum):
    DRAFT = "draft"
    REGISTRATION = "registration"
    LIVE = "live"
    ENDED = "ended"
    ARCHIVED = "archived"


class EmailStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"


class VoucherStatus(str, enum.Enum):
    AVAILABLE = "available"
    CLAIMED = "claimed"
    EXPIRED = "expired"


class PrizeStatus(str, enum.Enum):
    PENDING = "pending"
    CLAIMED = "claimed"
    EXPIRED = "expired"


class ProviderType(str, enum.Enum):
    SMTP = "smtp"
    BREVO = "brevo"
    MAILGUN = "mailgun"
    AWS_SES = "aws_ses"
    MAILJET = "mailjet"
    GMAIL = "gmail"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    SENDING = "sending"
    PAUSED = "paused"
    SENT = "sent"
    CANCELLED = "cancelled"


class AuditAction(str, enum.Enum):
    ACCOUNT_REGISTER = "account.register"
    ACCOUNT_LOGIN = "account.login"
    ACCOUNT_LOGOUT = "account.logout"
    ACCOUNT_VERIFY_EMAIL = "account.verify_email"
    ACCOUNT_PASSWORD_RESET = "account.password_reset"
    ACCOUNT_LOCKED = "account.locked"

    EVENT_CREATE = "event.create"
    EVENT_UPDATE = "event.update"
    EVENT_DELETE = "event.delete"
    EVENT_SYNC = "event.sync"
    EVENT_FINALIZE = "event.finalize"

    PRIZE_ASSIGN = "prize.assign"
    PRIZE_CLAIM = "prize.claim"

    VOUCHER_UPLOAD = "voucher.upload"
    VOUCHER_CLAIM = "voucher.claim"

    CERTIFICATE_GENERATE = "certificate.generate"
    CERTIFICATE_DOWNLOAD = "certificate.download"
    CERTIFICATE_VERIFY = "certificate.verify"

    EMAIL_SEND = "email.send"
    EMAIL_CAMPAIGN_SEND = "email.campaign_send"

    ADMIN_PROVIDER_CREATE = "admin.provider_create"
    ADMIN_PROVIDER_UPDATE = "admin.provider_update"
    ADMIN_PROVIDER_DELETE = "admin.provider_delete"
    ADMIN_IMPORT_PARTICIPANTS = "admin.import_participants"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    # platform operators (admins/organizers), separate from event participants
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), default=UserRole.ORGANIZER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    events: Mapped[List["Event"]] = relationship(
        "Event", back_populates="created_by_user", lazy="selectin"
    )
    campaigns: Mapped[List["EmailCampaign"]] = relationship(
        "EmailCampaign", back_populates="created_by_user", lazy="selectin"
    )


class Event(TimestampMixin, Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    registration_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    registration_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    event_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    event_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    status: Mapped[EventStatus] = mapped_column(
        Enum(EventStatus), default=EventStatus.REGISTRATION, nullable=False
    )

    ctfd_url: Mapped[Optional[str]] = mapped_column(String(500))
    ctfd_api_key: Mapped[Optional[str]] = mapped_column(Text)  # encrypted
    ctfd_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    settings: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_by_user: Mapped["User"] = relationship("User", back_populates="events")

    participants: Mapped[List["Participant"]] = relationship(
        "Participant", back_populates="event", lazy="selectin", cascade="all, delete-orphan"
    )
    teams: Mapped[List["Team"]] = relationship(
        "Team", back_populates="event", lazy="selectin", cascade="all, delete-orphan"
    )
    voucher_pools: Mapped[List["VoucherPool"]] = relationship(
        "VoucherPool", back_populates="event", lazy="selectin", cascade="all, delete-orphan"
    )
    prize_rules: Mapped[List["PrizeRule"]] = relationship(
        "PrizeRule", back_populates="event", lazy="selectin", cascade="all, delete-orphan"
    )
    certificate_templates: Mapped[List["CertificateTemplate"]] = relationship(
        "CertificateTemplate", back_populates="event", lazy="selectin", cascade="all, delete-orphan"
    )
    email_templates: Mapped[List["EmailTemplate"]] = relationship(
        "EmailTemplate", back_populates="event", lazy="selectin", cascade="all, delete-orphan"
    )
    campaigns: Mapped[List["EmailCampaign"]] = relationship(
        "EmailCampaign", back_populates="event", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_events_status", "status"),
        Index("idx_events_slug", "slug"),
    )


class Participant(TimestampMixin, Base):
    __tablename__ = "participants"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    event_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))

    ctfd_user_id: Mapped[Optional[int]] = mapped_column(Integer)
    ctfd_provisioned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(255))
    email_verification_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    magic_link_token: Mapped[Optional[str]] = mapped_column(String(255))
    magic_link_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    magic_link_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    final_rank: Mapped[Optional[int]] = mapped_column(Integer)
    final_score: Mapped[Optional[float]] = mapped_column(Float)

    registration_ip: Mapped[Optional[str]] = mapped_column(INET)
    login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    extra_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    source: Mapped[str] = mapped_column(
        String(50), default="registration", nullable=False
    )  # 'registration' or 'import'

    # noload by default for list views; load explicitly when needed
    event: Mapped["Event"] = relationship("Event", back_populates="participants")
    team_memberships: Mapped[List["TeamMember"]] = relationship(
        "TeamMember", back_populates="participant", lazy="noload", cascade="all, delete-orphan"
    )
    prizes: Mapped[List["Prize"]] = relationship(
        "Prize", back_populates="participant", lazy="noload", cascade="all, delete-orphan"
    )
    certificates: Mapped[List["Certificate"]] = relationship(
        "Certificate", back_populates="participant", lazy="noload", cascade="all, delete-orphan"
    )
    email_logs: Mapped[List["EmailLog"]] = relationship(
        "EmailLog", back_populates="participant", lazy="noload", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("event_id", "email", name="uq_participant_event_email"),
        UniqueConstraint("event_id", "username", name="uq_participant_event_username"),
        Index("idx_participants_event", "event_id"),
        Index("idx_participants_email", "email"),
        Index("idx_participants_ctfd_user_id", "ctfd_user_id"),
        Index("idx_participants_event_created", "event_id", "created_at"),  # for sorted list queries
    )


class Team(TimestampMixin, Base):
    # synced from ctfd after event
    __tablename__ = "teams"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    event_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ctfd_team_id: Mapped[Optional[int]] = mapped_column(Integer)

    final_rank: Mapped[Optional[int]] = mapped_column(Integer)
    final_score: Mapped[Optional[float]] = mapped_column(Float)

    captain_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id")
    )

    event: Mapped["Event"] = relationship("Event", back_populates="teams")
    members: Mapped[List["TeamMember"]] = relationship(
        "TeamMember", back_populates="team", lazy="selectin", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("event_id", "ctfd_team_id", name="uq_team_event_ctfd"),
        Index("idx_teams_event", "event_id"),
    )


class TeamMember(Base):
    # m2m between teams and participants
    __tablename__ = "team_members"

    team_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id"), primary_key=True
    )
    participant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id"), primary_key=True
    )
    is_captain: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    team: Mapped["Team"] = relationship("Team", back_populates="members")
    participant: Mapped["Participant"] = relationship("Participant", back_populates="team_memberships")


class EmailProvider(TimestampMixin, Base):
    __tablename__ = "email_providers"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(ProviderType), nullable=False
    )

    # encrypted json config -- smtp: {host, port, username, password, use_tls}; api: {api_key, domain, region, ...}
    config: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # rate limits; nullable = no limit
    daily_limit: Mapped[Optional[int]] = mapped_column(Integer)
    hourly_limit: Mapped[Optional[int]] = mapped_column(Integer)
    minute_limit: Mapped[Optional[int]] = mapped_column(Integer)
    second_limit: Mapped[Optional[int]] = mapped_column(Integer)
    monthly_limit: Mapped[Optional[int]] = mapped_column(Integer)

    # lower = higher priority
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_healthy: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    last_error_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    circuit_open_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    email_logs: Mapped[List["EmailLog"]] = relationship(
        "EmailLog", back_populates="provider", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_providers_active_priority", "is_active", "priority"),
    )


class EmailTemplate(TimestampMixin, Base):
    # jinja2 syntax for variable substitution
    __tablename__ = "email_templates"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # global (event_id null) or event-specific
    event_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id")
    )

    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[Optional[str]] = mapped_column(Text)  # plain text fallback

    variables: Mapped[List[str]] = mapped_column(
        ARRAY(String), default=list, nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    event: Mapped[Optional["Event"]] = relationship("Event", back_populates="email_templates")

    __table_args__ = (
        UniqueConstraint("event_id", "slug", name="uq_email_template_event_slug"),
        Index("idx_email_templates_slug", "slug"),
    )


class EmailLog(TimestampMixin, Base):
    __tablename__ = "email_logs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )

    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    participant_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id")
    )

    provider_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_providers.id")
    )
    provider_name: Mapped[Optional[str]] = mapped_column(String(100))  # denormalized

    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    template_slug: Mapped[Optional[str]] = mapped_column(String(100))

    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus), default=EmailStatus.QUEUED, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    campaign_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_campaigns.id")
    )

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    participant: Mapped[Optional["Participant"]] = relationship(
        "Participant", back_populates="email_logs"
    )
    provider: Mapped[Optional["EmailProvider"]] = relationship(
        "EmailProvider", back_populates="email_logs"
    )
    campaign: Mapped[Optional["EmailCampaign"]] = relationship(
        "EmailCampaign", back_populates="email_logs"
    )

    __table_args__ = (
        Index("idx_email_logs_recipient", "recipient_email"),
        Index("idx_email_logs_status", "status"),
        Index("idx_email_logs_sent_at", "sent_at"),
        Index("idx_email_logs_campaign", "campaign_id"),
    )


class EmailCampaign(TimestampMixin, Base):
    # bulk email campaigns (push mode)
    __tablename__ = "email_campaigns"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    event_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_html: Mapped[str] = mapped_column(Text, nullable=False)
    body_text: Mapped[Optional[str]] = mapped_column(Text)

    target_group: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'all', 'verified', 'unverified', 'top_n', 'rank_range', 'custom'
    target_config: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    # e.g. {"top_n": 10} or {"rank_from": 1, "rank_to": 50} or {"emails": [...]}

    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False
    )
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    total_recipients: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sent_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    event: Mapped["Event"] = relationship("Event", back_populates="campaigns")
    created_by_user: Mapped["User"] = relationship("User", back_populates="campaigns")
    email_logs: Mapped[List["EmailLog"]] = relationship(
        "EmailLog", back_populates="campaign", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_campaigns_event", "event_id"),
        Index("idx_campaigns_status", "status"),
    )


class VoucherPool(TimestampMixin, Base):
    __tablename__ = "voucher_pools"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    event_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    platform: Mapped[Optional[str]] = mapped_column(String(100))  # 'hackthebox', 'tryhackme', etc.

    total_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    claimed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    event: Mapped["Event"] = relationship("Event", back_populates="voucher_pools")
    vouchers: Mapped[List["Voucher"]] = relationship(
        "Voucher", back_populates="pool", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_voucher_pools_event", "event_id"),
    )


class Voucher(TimestampMixin, Base):
    __tablename__ = "vouchers"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    pool_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("voucher_pools.id"), nullable=False
    )

    code: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[VoucherStatus] = mapped_column(
        Enum(VoucherStatus), default=VoucherStatus.AVAILABLE, nullable=False
    )

    claimed_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id")
    )
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    pool: Mapped["VoucherPool"] = relationship("VoucherPool", back_populates="vouchers")

    __table_args__ = (
        Index("idx_vouchers_pool_status", "pool_id", "status"),
    )


class PrizeRule(TimestampMixin, Base):
    __tablename__ = "prize_rules"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    event_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # rank range (inclusive)
    rank_from: Mapped[int] = mapped_column(Integer, nullable=False)
    rank_to: Mapped[int] = mapped_column(Integer, nullable=False)

    voucher_pool_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("voucher_pools.id")
    )

    certificate_template_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certificate_templates.id")
    )

    custom_prize: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)

    # for overlapping ranges
    priority: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    event: Mapped["Event"] = relationship("Event", back_populates="prize_rules")

    __table_args__ = (
        Index("idx_prize_rules_event", "event_id"),
    )


class Prize(TimestampMixin, Base):
    __tablename__ = "prizes"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    participant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False
    )

    prize_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 'voucher', 'certificate', 'custom'

    prize_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )
    # voucher: {voucher_id, code, platform}; certificate: {certificate_id, verification_code}; custom: {title, description, value, ...}

    status: Mapped[PrizeStatus] = mapped_column(
        Enum(PrizeStatus), default=PrizeStatus.PENDING, nullable=False
    )
    claimed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    rule_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prize_rules.id")
    )
    assigned_manually: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    participant: Mapped["Participant"] = relationship("Participant", back_populates="prizes")

    __table_args__ = (
        Index("idx_prizes_participant", "participant_id"),
        Index("idx_prizes_status", "status"),
    )


class CertificateTemplate(TimestampMixin, Base):
    __tablename__ = "certificate_templates"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    # global (event_id null) or event-specific
    event_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("events.id"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    template_file: Mapped[str] = mapped_column(String(500), nullable=False)
    # path relative to storage

    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    # each zone: {id, field, x, y, width, height, font_family, font_size, font_color, alignment, rotation}
    text_zones: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONB, default=list, nullable=False
    )

    qr_zone: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    # {x, y, size}

    output_format: Mapped[str] = mapped_column(String(10), default="pdf", nullable=False)

    # rank range this template applies to
    rank_from: Mapped[Optional[int]] = mapped_column(Integer)
    rank_to: Mapped[Optional[int]] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    event: Mapped[Optional["Event"]] = relationship("Event", back_populates="certificate_templates")
    certificates: Mapped[List["Certificate"]] = relationship(
        "Certificate", back_populates="template", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_cert_templates_event", "event_id"),
    )


class Certificate(TimestampMixin, Base):
    __tablename__ = "certificates"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    participant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id"), nullable=False
    )
    template_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("certificate_templates.id"), nullable=False
    )

    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    team_name: Mapped[Optional[str]] = mapped_column(String(255))
    rank: Mapped[Optional[int]] = mapped_column(Integer)

    verification_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    file_path: Mapped[Optional[str]] = mapped_column(String(500))

    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    download_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    name_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edit_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    participant: Mapped["Participant"] = relationship(
        "Participant", back_populates="certificates"
    )
    template: Mapped["CertificateTemplate"] = relationship(
        "CertificateTemplate", back_populates="certificates"
    )

    __table_args__ = (
        Index("idx_certificates_participant", "participant_id"),
        Index("idx_certificates_verification_code", "verification_code"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    participant_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # 'user', 'participant', 'system'

    action: Mapped[str] = mapped_column(String(100), nullable=False)

    resource_type: Mapped[Optional[str]] = mapped_column(String(50))
    resource_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True))

    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    extra_data: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, default=dict, nullable=False
    )

    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    __table_args__ = (
        Index("idx_audit_logs_timestamp", "timestamp"),
        Index("idx_audit_logs_user", "user_id", "timestamp"),
        Index("idx_audit_logs_participant", "participant_id", "timestamp"),
        Index("idx_audit_logs_action", "action", "timestamp"),
    )


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)

    user_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    participant_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("participants.id")
    )

    data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    ip_address: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_sessions_user", "user_id"),
        Index("idx_sessions_participant", "participant_id"),
        Index("idx_sessions_expires", "expires_at"),
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
