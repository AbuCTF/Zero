"""Add abuse prevention fields to certificates

Revision ID: 002
Revises: 001
Create Date: 2024-06-13

Adds:
- name_locked: bool - prevents further name edits after download
- edit_count: int - tracks number of display name edits
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add name_locked column (defaults to False for existing certs)
    op.add_column(
        "certificates",
        sa.Column("name_locked", sa.Boolean(), nullable=False, server_default="false")
    )
    
    # Add edit_count column (defaults to 0 for existing certs)
    op.add_column(
        "certificates",
        sa.Column("edit_count", sa.Integer(), nullable=False, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("certificates", "edit_count")
    op.drop_column("certificates", "name_locked")
