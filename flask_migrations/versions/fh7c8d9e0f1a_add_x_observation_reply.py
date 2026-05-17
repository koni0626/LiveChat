"""add x observation reply

Revision ID: fh7c8d9e0f1a
Revises: fg6b7c8d9e0f
Create Date: 2026-05-17 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "fh7c8d9e0f1a"
down_revision = "fg6b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "x_observation_reply",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("target_tweet_id", sa.String(length=100), nullable=False),
        sa.Column("target_author_id", sa.String(length=100), nullable=True),
        sa.Column("target_author_name", sa.String(length=255), nullable=True),
        sa.Column("target_author_username", sa.String(length=255), nullable=True),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("replied_by_user_id", sa.Integer(), nullable=False),
        sa.Column("reply_text", sa.Text(), nullable=False),
        sa.Column("reply_x_post_id", sa.String(length=100), nullable=True),
        sa.Column("reply_url", sa.String(length=512), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["replied_by_user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_x_observation_reply_project_id"), "x_observation_reply", ["project_id"], unique=False)
    op.create_index(op.f("ix_x_observation_reply_target_tweet_id"), "x_observation_reply", ["target_tweet_id"], unique=False)
    op.create_index(op.f("ix_x_observation_reply_target_author_id"), "x_observation_reply", ["target_author_id"], unique=False)
    op.create_index(op.f("ix_x_observation_reply_target_author_username"), "x_observation_reply", ["target_author_username"], unique=False)
    op.create_index(op.f("ix_x_observation_reply_character_id"), "x_observation_reply", ["character_id"], unique=False)
    op.create_index(op.f("ix_x_observation_reply_replied_by_user_id"), "x_observation_reply", ["replied_by_user_id"], unique=False)
    op.create_index(op.f("ix_x_observation_reply_reply_x_post_id"), "x_observation_reply", ["reply_x_post_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_x_observation_reply_reply_x_post_id"), table_name="x_observation_reply")
    op.drop_index(op.f("ix_x_observation_reply_replied_by_user_id"), table_name="x_observation_reply")
    op.drop_index(op.f("ix_x_observation_reply_character_id"), table_name="x_observation_reply")
    op.drop_index(op.f("ix_x_observation_reply_target_author_username"), table_name="x_observation_reply")
    op.drop_index(op.f("ix_x_observation_reply_target_author_id"), table_name="x_observation_reply")
    op.drop_index(op.f("ix_x_observation_reply_target_tweet_id"), table_name="x_observation_reply")
    op.drop_index(op.f("ix_x_observation_reply_project_id"), table_name="x_observation_reply")
    op.drop_table("x_observation_reply")
