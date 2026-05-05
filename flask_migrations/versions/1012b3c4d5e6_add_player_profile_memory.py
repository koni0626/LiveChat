"""add player profile memory

Revision ID: 1012b3c4d5e6
Revises: 1011a2b3c4d5
Create Date: 2026-05-05 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "1012b3c4d5e6"
down_revision = "1011a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "player_profile_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("interest_notes", sa.Text(), nullable=True),
        sa.Column("dislike_notes", sa.Text(), nullable=True),
        sa.Column("conversation_style_notes", sa.Text(), nullable=True),
        sa.Column("humor_notes", sa.Text(), nullable=True),
        sa.Column("romance_notes", sa.Text(), nullable=True),
        sa.Column("goal_notes", sa.Text(), nullable=True),
        sa.Column("frustration_notes", sa.Text(), nullable=True),
        sa.Column("recent_player_notes", sa.Text(), nullable=True),
        sa.Column("profile_json", sa.Text(), nullable=True),
        sa.Column("last_interaction_at", sa.DateTime(), nullable=True),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_player_profile_memory_user"),
    )
    op.create_index(op.f("ix_player_profile_memory_user_id"), "player_profile_memory", ["user_id"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_player_profile_memory_user_id"), table_name="player_profile_memory")
    op.drop_table("player_profile_memory")
