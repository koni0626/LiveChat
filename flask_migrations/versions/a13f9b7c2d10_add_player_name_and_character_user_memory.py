"""add player_name and character_user_memory

Revision ID: a13f9b7c2d10
Revises: f1a2b3c4d5e6
Create Date: 2026-05-01 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a13f9b7c2d10"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("user", sa.Column("player_name", sa.String(length=100), nullable=True))
    op.execute("UPDATE \"user\" SET player_name = display_name WHERE player_name IS NULL OR player_name = ''")

    op.create_table(
        "character_user_memory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("relationship_summary", sa.Text(), nullable=True),
        sa.Column("memory_notes", sa.Text(), nullable=True),
        sa.Column("preference_notes", sa.Text(), nullable=True),
        sa.Column("unresolved_threads", sa.Text(), nullable=True),
        sa.Column("important_events", sa.Text(), nullable=True),
        sa.Column("last_interaction_at", sa.DateTime(), nullable=True),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "character_id", name="uq_character_user_memory_user_character"),
    )
    op.create_index(op.f("ix_character_user_memory_user_id"), "character_user_memory", ["user_id"], unique=False)
    op.create_index(op.f("ix_character_user_memory_character_id"), "character_user_memory", ["character_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_character_user_memory_character_id"), table_name="character_user_memory")
    op.drop_index(op.f("ix_character_user_memory_user_id"), table_name="character_user_memory")
    op.drop_table("character_user_memory")
    op.drop_column("user", "player_name")
