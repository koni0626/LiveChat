"""add cinema novel review

Revision ID: 1005a6b7c8d9
Revises: d46f0a2b3c55
Create Date: 2026-05-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "1005a6b7c8d9"
down_revision = "d46f0a2b3c55"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "cinema_novel_review" in inspect(bind).get_table_names():
        return
    op.create_table(
        "cinema_novel_review",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("novel_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("feed_post_id", sa.Integer(), nullable=True),
        sa.Column("memory_note_id", sa.Integer(), nullable=True),
        sa.Column("review_text", sa.Text(), nullable=False),
        sa.Column("memory_note", sa.Text(), nullable=True),
        sa.Column("rating_label", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="published"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["feed_post_id"], ["feed_post.id"]),
        sa.ForeignKeyConstraint(["memory_note_id"], ["character_memory_note.id"]),
        sa.ForeignKeyConstraint(["novel_id"], ["cinema_novel.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "character_id", "user_id", name="uq_cinema_novel_review_novel_character_user"),
    )
    op.create_index(op.f("ix_cinema_novel_review_character_id"), "cinema_novel_review", ["character_id"], unique=False)
    op.create_index(op.f("ix_cinema_novel_review_feed_post_id"), "cinema_novel_review", ["feed_post_id"], unique=False)
    op.create_index(op.f("ix_cinema_novel_review_memory_note_id"), "cinema_novel_review", ["memory_note_id"], unique=False)
    op.create_index(op.f("ix_cinema_novel_review_novel_id"), "cinema_novel_review", ["novel_id"], unique=False)
    op.create_index(op.f("ix_cinema_novel_review_status"), "cinema_novel_review", ["status"], unique=False)
    op.create_index(op.f("ix_cinema_novel_review_user_id"), "cinema_novel_review", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_cinema_novel_review_user_id"), table_name="cinema_novel_review")
    op.drop_index(op.f("ix_cinema_novel_review_status"), table_name="cinema_novel_review")
    op.drop_index(op.f("ix_cinema_novel_review_novel_id"), table_name="cinema_novel_review")
    op.drop_index(op.f("ix_cinema_novel_review_memory_note_id"), table_name="cinema_novel_review")
    op.drop_index(op.f("ix_cinema_novel_review_feed_post_id"), table_name="cinema_novel_review")
    op.drop_index(op.f("ix_cinema_novel_review_character_id"), table_name="cinema_novel_review")
    op.drop_table("cinema_novel_review")
