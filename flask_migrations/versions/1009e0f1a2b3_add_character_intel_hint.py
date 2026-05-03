"""add character intel hint

Revision ID: 1009e0f1a2b3
Revises: 1008d9e0f1a2
Create Date: 2026-05-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "1009e0f1a2b3"
down_revision = "1008d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "character_intel_hint",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("target_character_id", sa.Integer(), nullable=False),
        sa.Column("source_character_id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("hint_text", sa.Text(), nullable=False),
        sa.Column("reveal_threshold", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="revealed"),
        sa.Column("revealed_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["source_character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["target_character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "target_character_id",
            "source_character_id",
            "topic",
            name="uq_character_intel_hint_user_target_source_topic",
        ),
    )
    op.create_index(op.f("ix_character_intel_hint_user_id"), "character_intel_hint", ["user_id"], unique=False)
    op.create_index(op.f("ix_character_intel_hint_project_id"), "character_intel_hint", ["project_id"], unique=False)
    op.create_index(op.f("ix_character_intel_hint_target_character_id"), "character_intel_hint", ["target_character_id"], unique=False)
    op.create_index(op.f("ix_character_intel_hint_source_character_id"), "character_intel_hint", ["source_character_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_character_intel_hint_source_character_id"), table_name="character_intel_hint")
    op.drop_index(op.f("ix_character_intel_hint_target_character_id"), table_name="character_intel_hint")
    op.drop_index(op.f("ix_character_intel_hint_project_id"), table_name="character_intel_hint")
    op.drop_index(op.f("ix_character_intel_hint_user_id"), table_name="character_intel_hint")
    op.drop_table("character_intel_hint")
