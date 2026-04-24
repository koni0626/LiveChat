"""add session gift event

Revision ID: f2a6c0e91b44
Revises: 8c1b7f2e4d11
Create Date: 2026-04-25 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f2a6c0e91b44"
down_revision = "8c1b7f2e4d11"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "session_gift_event",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("gift_direction", sa.String(length=50), nullable=False),
        sa.Column("recognized_label", sa.String(length=255), nullable=True),
        sa.Column("recognized_tags_json", sa.Text(), nullable=True),
        sa.Column("reaction_summary", sa.Text(), nullable=True),
        sa.Column("evaluation_delta", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["chat_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("session_gift_event", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_session_gift_event_session_id"), ["session_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_session_gift_event_character_id"), ["character_id"], unique=False)


def downgrade():
    with op.batch_alter_table("session_gift_event", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_session_gift_event_character_id"))
        batch_op.drop_index(batch_op.f("ix_session_gift_event_session_id"))
    op.drop_table("session_gift_event")
