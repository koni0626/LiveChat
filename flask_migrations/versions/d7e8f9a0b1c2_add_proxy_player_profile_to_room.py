"""add proxy player profile to room

Revision ID: d7e8f9a0b1c2
Revises: c5d6e7f8a9b0
Create Date: 2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = "d7e8f9a0b1c2"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("live_chat_room", schema=None) as batch_op:
        batch_op.add_column(sa.Column("proxy_player_gender", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("proxy_player_speech_style", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("live_chat_room", schema=None) as batch_op:
        batch_op.drop_column("proxy_player_speech_style")
        batch_op.drop_column("proxy_player_gender")
