"""add world location image prompt

Revision ID: f8c9d0e1f2a3
Revises: f7b8c9d0e1f2
Create Date: 2026-04-29 15:15:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f8c9d0e1f2a3"
down_revision = "f7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("world_location", sa.Column("image_prompt", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("world_location", "image_prompt")
