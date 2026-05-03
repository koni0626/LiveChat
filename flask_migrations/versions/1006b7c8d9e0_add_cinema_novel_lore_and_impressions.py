"""add cinema novel lore and impressions

Revision ID: 1006b7c8d9e0
Revises: 1005a6b7c8d9
Create Date: 2026-05-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "1006b7c8d9e0"
down_revision = "1005a6b7c8d9"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    if "cinema_novel_lore_entry" not in existing_tables:
        op.create_table(
            "cinema_novel_lore_entry",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("novel_id", sa.Integer(), nullable=False),
            sa.Column("lore_type", sa.String(length=50), nullable=False, server_default="other"),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("role_note", sa.Text(), nullable=True),
            sa.Column("source_note", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["novel_id"], ["cinema_novel.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("novel_id", "lore_type", "name", name="uq_cinema_novel_lore_entry_novel_type_name"),
        )
        op.create_index(op.f("ix_cinema_novel_lore_entry_lore_type"), "cinema_novel_lore_entry", ["lore_type"], unique=False)
        op.create_index(op.f("ix_cinema_novel_lore_entry_novel_id"), "cinema_novel_lore_entry", ["novel_id"], unique=False)

    if "cinema_novel_character_impression" not in existing_tables:
        op.create_table(
            "cinema_novel_character_impression",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("novel_id", sa.Integer(), nullable=False),
            sa.Column("reviewer_character_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("target_name", sa.String(length=255), nullable=False),
            sa.Column("target_character_id", sa.Integer(), nullable=True),
            sa.Column("impression_text", sa.Text(), nullable=False),
            sa.Column("talk_hint", sa.Text(), nullable=True),
            sa.Column("memory_note_id", sa.Integer(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["memory_note_id"], ["character_memory_note.id"]),
            sa.ForeignKeyConstraint(["novel_id"], ["cinema_novel.id"]),
            sa.ForeignKeyConstraint(["reviewer_character_id"], ["character.id"]),
            sa.ForeignKeyConstraint(["target_character_id"], ["character.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "novel_id",
                "reviewer_character_id",
                "user_id",
                "target_name",
                name="uq_cinema_novel_character_impression_unique_target",
            ),
        )
        op.create_index(op.f("ix_cinema_novel_character_impression_memory_note_id"), "cinema_novel_character_impression", ["memory_note_id"], unique=False)
        op.create_index(op.f("ix_cinema_novel_character_impression_novel_id"), "cinema_novel_character_impression", ["novel_id"], unique=False)
        op.create_index(op.f("ix_cinema_novel_character_impression_reviewer_character_id"), "cinema_novel_character_impression", ["reviewer_character_id"], unique=False)
        op.create_index(op.f("ix_cinema_novel_character_impression_target_character_id"), "cinema_novel_character_impression", ["target_character_id"], unique=False)
        op.create_index(op.f("ix_cinema_novel_character_impression_user_id"), "cinema_novel_character_impression", ["user_id"], unique=False)


def downgrade():
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    if "cinema_novel_character_impression" in existing_tables:
        op.drop_index(op.f("ix_cinema_novel_character_impression_user_id"), table_name="cinema_novel_character_impression")
        op.drop_index(op.f("ix_cinema_novel_character_impression_target_character_id"), table_name="cinema_novel_character_impression")
        op.drop_index(op.f("ix_cinema_novel_character_impression_reviewer_character_id"), table_name="cinema_novel_character_impression")
        op.drop_index(op.f("ix_cinema_novel_character_impression_novel_id"), table_name="cinema_novel_character_impression")
        op.drop_index(op.f("ix_cinema_novel_character_impression_memory_note_id"), table_name="cinema_novel_character_impression")
        op.drop_table("cinema_novel_character_impression")
    if "cinema_novel_lore_entry" in existing_tables:
        op.drop_index(op.f("ix_cinema_novel_lore_entry_novel_id"), table_name="cinema_novel_lore_entry")
        op.drop_index(op.f("ix_cinema_novel_lore_entry_lore_type"), table_name="cinema_novel_lore_entry")
        op.drop_table("cinema_novel_lore_entry")
