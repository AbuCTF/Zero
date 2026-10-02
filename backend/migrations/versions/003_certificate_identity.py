import sqlalchemy as sa
from alembic import op

revision = "003_certificate_identity"
down_revision = "002_certificate_abuse_prevention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "certificate_templates",
        sa.Column(
            "certificate_prefix",
            sa.String(length=20),
            server_default="CERT",
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        "uq_certificates_participant_template",
        "certificates",
        ["participant_id", "template_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_certificates_participant_template",
        "certificates",
        type_="unique",
    )
    op.drop_column("certificate_templates", "certificate_prefix")
