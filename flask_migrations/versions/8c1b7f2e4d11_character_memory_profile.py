"""character memory profile

Revision ID: 8c1b7f2e4d11
Revises: 1f3d5f0e8a21
Create Date: 2026-04-25 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "8c1b7f2e4d11"
down_revision = "1f3d5f0e8a21"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.add_column(sa.Column("memory_profile_json", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.drop_column("memory_profile_json")
