"""add proxy player objective to room

Revision ID: c5d6e7f8a9b0
Revises: b4a9c2d7e8f1
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "c5d6e7f8a9b0"
down_revision = "b4a9c2d7e8f1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("live_chat_room", schema=None) as batch_op:
        batch_op.add_column(sa.Column("proxy_player_objective", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("live_chat_room", schema=None) as batch_op:
        batch_op.drop_column("proxy_player_objective")
