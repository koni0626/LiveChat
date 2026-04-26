"""add character gender

Revision ID: f4c2b8a1d9e0
Revises: e7a1c3d9f0b2
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f4c2b8a1d9e0"
down_revision = "e7a1c3d9f0b2"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.add_column(sa.Column("gender", sa.String(length=100), nullable=True))


def downgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.drop_column("gender")
