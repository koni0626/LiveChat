"""rename character role to nickname

Revision ID: d2f4a9b8c6e1
Revises: c8e4d1f0a2b3
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d2f4a9b8c6e1"
down_revision = "c8e4d1f0a2b3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.alter_column("role", new_column_name="nickname", existing_type=sa.String(length=100))


def downgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.alter_column("nickname", new_column_name="role", existing_type=sa.String(length=100))
