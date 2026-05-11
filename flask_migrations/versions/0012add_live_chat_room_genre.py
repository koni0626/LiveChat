"""add live chat room genre

Revision ID: 0012addroomgenre
Revises: ff5a6b7c8d9e
Create Date: 2026-05-10
"""

from alembic import op
import sqlalchemy as sa


revision = "0012addroomgenre"
down_revision = "ff5a6b7c8d9e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("live_chat_room") as batch_op:
        batch_op.add_column(sa.Column("genre", sa.String(length=50), nullable=False, server_default="romance"))
        batch_op.create_index(batch_op.f("ix_live_chat_room_genre"), ["genre"], unique=False)

    with op.batch_alter_table("live_chat_room") as batch_op:
        batch_op.alter_column("genre", server_default=None)


def downgrade():
    with op.batch_alter_table("live_chat_room") as batch_op:
        batch_op.drop_index(batch_op.f("ix_live_chat_room_genre"))
        batch_op.drop_column("genre")
