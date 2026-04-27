"""add feed feature

Revision ID: b4a9c2d7e8f1
Revises: a1b2c3d4e5f6
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa


revision = "b4a9c2d7e8f1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "feed_post",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("image_asset_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("generation_state_json", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["image_asset_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_feed_post_project_id"), "feed_post", ["project_id"], unique=False)
    op.create_index(op.f("ix_feed_post_character_id"), "feed_post", ["character_id"], unique=False)
    op.create_index(op.f("ix_feed_post_created_by_user_id"), "feed_post", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_feed_post_status"), "feed_post", ["status"], unique=False)
    op.create_index("ix_feed_post_status_published_at", "feed_post", ["status", "published_at"], unique=False)

    op.create_table(
        "feed_like",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("feed_post_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["feed_post_id"], ["feed_post.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feed_post_id", "user_id", name="uq_feed_like_post_user"),
    )
    op.create_index(op.f("ix_feed_like_feed_post_id"), "feed_like", ["feed_post_id"], unique=False)
    op.create_index(op.f("ix_feed_like_user_id"), "feed_like", ["user_id"], unique=False)

    op.create_table(
        "character_feed_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("profile_text", sa.Text(), nullable=True),
        sa.Column("source_post_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_latest_post_id", sa.Integer(), nullable=True),
        sa.Column("summary_state_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["source_latest_post_id"], ["feed_post.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id"),
    )
    op.create_index(op.f("ix_character_feed_profile_character_id"), "character_feed_profile", ["character_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_character_feed_profile_character_id"), table_name="character_feed_profile")
    op.drop_table("character_feed_profile")
    op.drop_index(op.f("ix_feed_like_user_id"), table_name="feed_like")
    op.drop_index(op.f("ix_feed_like_feed_post_id"), table_name="feed_like")
    op.drop_table("feed_like")
    op.drop_index("ix_feed_post_status_published_at", table_name="feed_post")
    op.drop_index(op.f("ix_feed_post_status"), table_name="feed_post")
    op.drop_index(op.f("ix_feed_post_created_by_user_id"), table_name="feed_post")
    op.drop_index(op.f("ix_feed_post_character_id"), table_name="feed_post")
    op.drop_index(op.f("ix_feed_post_project_id"), table_name="feed_post")
    op.drop_table("feed_post")
