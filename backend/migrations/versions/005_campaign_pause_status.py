from alembic import op

revision = "005_campaign_pause_status"
down_revision = "004_global_template_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'campaignstatus'
                  AND e.enumlabel = 'paused'
            ) AND NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'campaignstatus'
                  AND e.enumlabel = 'PAUSED'
            ) THEN
                ALTER TYPE campaignstatus RENAME VALUE 'paused' TO 'PAUSED';
            ELSIF NOT EXISTS (
                SELECT 1
                FROM pg_type t
                JOIN pg_enum e ON e.enumtypid = t.oid
                WHERE t.typname = 'campaignstatus'
                  AND e.enumlabel = 'PAUSED'
            ) THEN
                ALTER TYPE campaignstatus ADD VALUE 'PAUSED';
            END IF;
        END
        $$
        """
    )


def downgrade() -> None:
    pass
