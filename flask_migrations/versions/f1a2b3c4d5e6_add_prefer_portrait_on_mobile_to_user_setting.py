"""add prefer portrait on mobile to user setting

Revision ID: f1a2b3c4d5e6
Revises: f06b7c8d9e0f
Create Date: 2026-05-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f1a2b3c4d5e6"
down_revision = "f06b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_setting",
        sa.Column("prefer_portrait_on_mobile", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column("user_setting", "prefer_portrait_on_mobile")
