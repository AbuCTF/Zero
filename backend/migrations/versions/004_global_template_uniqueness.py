import sqlalchemy as sa
from alembic import op

revision = "004_global_template_uniqueness"
down_revision = "003_certificate_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"]: column
        for column in sa.inspect(bind).get_columns("email_templates")
    }
    if "slug" not in columns and "template_type" in columns:
        op.alter_column(
            "email_templates",
            "template_type",
            new_column_name="slug",
            existing_type=columns["template_type"]["type"],
        )
    if "description" not in columns:
        op.add_column(
            "email_templates",
            sa.Column("description", sa.Text(), nullable=True),
        )
    if not isinstance(columns["variables"]["type"], sa.ARRAY):
        op.execute(
            """
            CREATE FUNCTION pg_temp.jsonb_text_array(value jsonb)
            RETURNS varchar[]
            LANGUAGE sql
            IMMUTABLE
            AS $$
                SELECT COALESCE(array_agg(item), ARRAY[]::varchar[])
                FROM jsonb_array_elements_text(value) AS item
            $$
            """
        )
        op.execute(
            """
            ALTER TABLE email_templates
            ALTER COLUMN variables TYPE varchar[]
            USING pg_temp.jsonb_text_array(variables)
            """
        )
    op.execute(
        """
        DELETE FROM email_templates newer
        USING email_templates older
        WHERE newer.event_id IS NULL
          AND older.event_id IS NULL
          AND newer.slug = older.slug
          AND (
              newer.created_at > older.created_at
              OR (newer.created_at = older.created_at AND newer.id > older.id)
          )
        """
    )
    op.create_index(
        "uq_email_templates_global_slug",
        "email_templates",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("event_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_email_templates_global_slug",
        table_name="email_templates",
    )
