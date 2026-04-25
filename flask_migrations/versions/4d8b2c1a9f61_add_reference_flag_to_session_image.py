"""add reference flag to session image

Revision ID: 4d8b2c1a9f61
Revises: f2a6c0e91b44
Create Date: 2026-04-25 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "4d8b2c1a9f61"
down_revision = "f2a6c0e91b44"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("session_image", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_reference", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    with op.batch_alter_table("session_image", schema=None) as batch_op:
        batch_op.drop_column("is_reference")
