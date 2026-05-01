"""add character_memory_note

Revision ID: b24d8e6f9a31
Revises: a13f9b7c2d10
Create Date: 2026-05-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "b24d8e6f9a31"
down_revision = "a13f9b7c2d10"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "character_memory_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, server_default="other"),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_character_memory_note_character_id"), "character_memory_note", ["character_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_character_memory_note_character_id"), table_name="character_memory_note")
    op.drop_table("character_memory_note")
