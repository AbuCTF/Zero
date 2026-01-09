"""Initial database schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'organizer', 'viewer')")
    op.execute("CREATE TYPE eventstatus AS ENUM ('draft', 'registration', 'live', 'completed', 'archived')")
    op.execute("CREATE TYPE providertype AS ENUM ('smtp', 'brevo', 'mailgun', 'aws_ses', 'mailjet', 'gmail')")
    op.execute("CREATE TYPE emailstatus AS ENUM ('draft', 'pending', 'processing', 'sent', 'failed', 'bounced')")
    op.execute("CREATE TYPE voucherstatus AS ENUM ('available', 'reserved', 'claimed', 'expired')")
    op.execute("CREATE TYPE prizestatus AS ENUM ('pending', 'available', 'claimed', 'expired')")

    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('role', sa.Enum('admin', 'organizer', 'viewer', name='userrole', create_type=False), 
                  default='organizer', nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('email_verified', sa.Boolean(), default=False, nullable=False),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), 
                  onupdate=sa.func.now(), nullable=False),
    )

    # Sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), 
                  nullable=False, index=True),
        sa.Column('token_hash', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Events table
    op.create_table(
        'events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'registration', 'live', 'completed', 'archived', 
                                     name='eventstatus', create_type=False), 
                  default='draft', nullable=False, index=True),
        sa.Column('registration_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('registration_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('event_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('event_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ctfd_url', sa.String(500), nullable=True),
        sa.Column('ctfd_api_key', sa.Text(), nullable=True),
        sa.Column('ctfd_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('settings', postgresql.JSONB(), default={}, nullable=False),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), 
                  onupdate=sa.func.now(), nullable=False),
    )

    # Teams table
    op.create_table(
        'teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('invite_code', sa.String(32), nullable=True, unique=True),
        sa.Column('ctfd_team_id', sa.Integer(), nullable=True),
        sa.Column('final_rank', sa.Integer(), nullable=True),
        sa.Column('final_score', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    op.create_index('ix_teams_event_name', 'teams', ['event_id', 'name'], unique=True)

    # Participants table
    op.create_table(
        'participants',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('email', sa.String(255), nullable=False, index=True),
        sa.Column('username', sa.String(100), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('email_verified', sa.Boolean(), default=False, nullable=False),
        sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('email_verification_token', sa.String(255), nullable=True),
        sa.Column('email_verification_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ctfd_user_id', sa.Integer(), nullable=True),
        sa.Column('ctfd_provisioned', sa.Boolean(), default=False, nullable=False),
        sa.Column('ctfd_provisioned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('final_rank', sa.Integer(), nullable=True),
        sa.Column('final_score', sa.Integer(), nullable=True),
        sa.Column('is_blocked', sa.Boolean(), default=False, nullable=False),
        sa.Column('block_reason', sa.Text(), nullable=True),
        sa.Column('source', sa.String(50), default='registration', nullable=False),
        sa.Column('extra_data', postgresql.JSONB(), default={}, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), 
                  onupdate=sa.func.now(), nullable=False),
    )
    
    op.create_index('ix_participants_event_email', 'participants', ['event_id', 'email'], unique=True)
    op.create_index('ix_participants_event_username', 'participants', ['event_id', 'username'], unique=True)

    # Team Members table
    op.create_table(
        'team_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('teams.id', ondelete='CASCADE'), nullable=False),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('participants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_captain', sa.Boolean(), default=False, nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    op.create_index('ix_team_members_unique', 'team_members', ['team_id', 'participant_id'], unique=True)

    # Email Providers table
    op.create_table(
        'email_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('provider_type', sa.Enum('smtp', 'brevo', 'mailgun', 'aws_ses', 'mailjet', 'gmail',
                                            name='providertype', create_type=False), nullable=False),
        sa.Column('config', postgresql.JSONB(), default={}, nullable=False),
        sa.Column('daily_limit', sa.Integer(), default=300, nullable=False),
        sa.Column('hourly_limit', sa.Integer(), default=50, nullable=False),
        sa.Column('minute_limit', sa.Integer(), default=10, nullable=False),
        sa.Column('second_limit', sa.Integer(), default=1, nullable=False),
        sa.Column('monthly_limit', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Integer(), default=0, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('is_healthy', sa.Boolean(), default=True, nullable=False),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_error_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), 
                  onupdate=sa.func.now(), nullable=False),
    )

    # Email Templates table
    op.create_table(
        'email_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('template_type', sa.String(50), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('variables', postgresql.JSONB(), default=[], nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), 
                  onupdate=sa.func.now(), nullable=False),
    )

    # Email Campaigns table
    op.create_table(
        'email_campaigns',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('email_templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('draft', 'pending', 'processing', 'sent', 'failed', 'bounced',
                                     name='emailstatus', create_type=False), 
                  default='draft', nullable=False, index=True),
        sa.Column('filter_criteria', postgresql.JSONB(), default={}, nullable=False),
        sa.Column('total_recipients', sa.Integer(), default=0, nullable=False),
        sa.Column('sent_count', sa.Integer(), default=0, nullable=False),
        sa.Column('failed_count', sa.Integer(), default=0, nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Email Logs table
    op.create_table(
        'email_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('participants.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('campaign_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('email_campaigns.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('email_templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('provider_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('email_providers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('recipient', sa.String(255), nullable=False),
        sa.Column('subject', sa.String(500), nullable=False),
        sa.Column('status', sa.Enum('draft', 'pending', 'processing', 'sent', 'failed', 'bounced',
                                     name='emailstatus', create_type=False), nullable=False),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bounced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Voucher Pools table
    op.create_table(
        'voucher_pools',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('platform', sa.String(100), nullable=True),
        sa.Column('total_count', sa.Integer(), default=0, nullable=False),
        sa.Column('claimed_count', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Vouchers table
    op.create_table(
        'vouchers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pool_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('voucher_pools.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('code', sa.String(500), nullable=False, unique=True),
        sa.Column('status', sa.Enum('available', 'reserved', 'claimed', 'expired',
                                     name='voucherstatus', create_type=False), 
                  default='available', nullable=False, index=True),
        sa.Column('claimed_by', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('participants.id', ondelete='SET NULL'), nullable=True),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Prize Rules table
    op.create_table(
        'prize_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rank_min', sa.Integer(), nullable=False),
        sa.Column('rank_max', sa.Integer(), nullable=True),
        sa.Column('prize_type', sa.String(50), nullable=False),
        sa.Column('prize_value', sa.Text(), nullable=True),
        sa.Column('voucher_pool_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('voucher_pools.id', ondelete='SET NULL'), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Prizes table
    op.create_table(
        'prizes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('participants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('prize_rule_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('prize_rules.id', ondelete='SET NULL'), nullable=True),
        sa.Column('voucher_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('vouchers.id', ondelete='SET NULL'), nullable=True),
        sa.Column('prize_type', sa.String(50), nullable=False),
        sa.Column('prize_value', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'available', 'claimed', 'expired',
                                     name='prizestatus', create_type=False), 
                  default='available', nullable=False),
        sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Certificate Templates table
    op.create_table(
        'certificate_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('events.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_path', sa.String(500), nullable=True),
        sa.Column('width', sa.Integer(), default=1920, nullable=False),
        sa.Column('height', sa.Integer(), default=1080, nullable=False),
        sa.Column('text_zones', postgresql.JSONB(), default=[], nullable=False),
        sa.Column('qr_zone', postgresql.JSONB(), nullable=True),
        sa.Column('is_default', sa.Boolean(), default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), 
                  onupdate=sa.func.now(), nullable=False),
    )

    # Certificates table
    op.create_table(
        'certificates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('participants.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('certificate_templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('verification_code', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('custom_text', postgresql.JSONB(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('downloaded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('download_count', sa.Integer(), default=0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Audit Logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('action', sa.String(100), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('participant_id', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('participants.id', ondelete='SET NULL'), nullable=True),
        sa.Column('actor_type', sa.String(20), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(), default={}, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), 
                  nullable=False, index=True),
    )

    # System Settings table
    op.create_table(
        'system_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('key', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('value', postgresql.JSONB(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), 
                  onupdate=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('system_settings')
    op.drop_table('audit_logs')
    op.drop_table('certificates')
    op.drop_table('certificate_templates')
    op.drop_table('prizes')
    op.drop_table('prize_rules')
    op.drop_table('vouchers')
    op.drop_table('voucher_pools')
    op.drop_table('email_logs')
    op.drop_table('email_campaigns')
    op.drop_table('email_templates')
    op.drop_table('email_providers')
    op.drop_table('team_members')
    op.drop_table('participants')
    op.drop_table('teams')
    op.drop_table('events')
    op.drop_table('sessions')
    op.drop_table('users')
    
    # Drop enum types
    op.execute("DROP TYPE IF EXISTS prizestatus")
    op.execute("DROP TYPE IF EXISTS voucherstatus")
    op.execute("DROP TYPE IF EXISTS emailstatus")
    op.execute("DROP TYPE IF EXISTS providertype")
    op.execute("DROP TYPE IF EXISTS eventstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
