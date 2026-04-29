"""add world location filters

Revision ID: f7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-04-29 14:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("world_location", sa.Column("region", sa.String(length=100), nullable=True))
    op.add_column("world_location", sa.Column("tags_json", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("world_location", "tags_json")
    op.drop_column("world_location", "region")
