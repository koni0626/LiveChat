"""add image ai provider to user setting

Revision ID: f9d0e1f2a3b4
Revises: f8c9d0e1f2a3
Create Date: 2026-04-29 16:50:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f9d0e1f2a3b4"
down_revision = "f8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "user_setting",
        sa.Column("image_ai_provider", sa.String(length=20), nullable=False, server_default="openai"),
    )


def downgrade():
    op.drop_column("user_setting", "image_ai_provider")
