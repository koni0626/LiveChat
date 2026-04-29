"""add trpg story tables

Revision ID: e3f4a5b6c7d8
Revises: d7e8f9a0b1c2
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e3f4a5b6c7d8"
down_revision = "d7e8f9a0b1c2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "story",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("story_mode", sa.String(length=100), nullable=False),
        sa.Column("config_markdown", sa.Text(), nullable=True),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("initial_state_json", sa.Text(), nullable=True),
        sa.Column("style_reference_asset_id", sa.Integer(), nullable=True),
        sa.Column("main_character_reference_asset_id", sa.Integer(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["main_character_reference_asset_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["style_reference_asset_id"], ["asset.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("story", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_story_character_id"), ["character_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_created_by_user_id"), ["created_by_user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_project_id"), ["project_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_story_mode"), ["story_mode"], unique=False)

    op.create_table(
        "story_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("story_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("privacy_status", sa.String(length=50), nullable=False),
        sa.Column("player_name", sa.String(length=100), nullable=True),
        sa.Column("active_image_id", sa.Integer(), nullable=True),
        sa.Column("story_snapshot_json", sa.Text(), nullable=True),
        sa.Column("settings_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["active_image_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["owner_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["story_id"], ["story.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("story_session", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_story_session_owner_user_id"), ["owner_user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_session_privacy_status"), ["privacy_status"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_session_project_id"), ["project_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_session_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_session_story_id"), ["story_id"], unique=False)

    op.create_table(
        "story_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("sender_type", sa.String(length=50), nullable=False),
        sa.Column("speaker_name", sa.String(length=255), nullable=True),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("message_type", sa.String(length=50), nullable=False),
        sa.Column("order_no", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["story_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("story_message", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_story_message_message_type"), ["message_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_message_sender_type"), ["sender_type"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_message_session_id"), ["session_id"], unique=False)

    op.create_table(
        "story_session_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["story_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("story_session_state", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_story_session_state_session_id"), ["session_id"], unique=True)

    op.create_table(
        "story_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("source_message_id", sa.Integer(), nullable=True),
        sa.Column("visual_type", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("reference_asset_ids_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["story_session.id"]),
        sa.ForeignKeyConstraint(["source_message_id"], ["story_message.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("story_image", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_story_image_asset_id"), ["asset_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_image_session_id"), ["session_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_image_source_message_id"), ["source_message_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_image_visual_type"), ["visual_type"], unique=False)

    op.create_table(
        "story_roll_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("formula", sa.String(length=100), nullable=False),
        sa.Column("dice_json", sa.Text(), nullable=False),
        sa.Column("modifier", sa.Integer(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("target", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(length=50), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["story_message.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["story_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("story_roll_log", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_story_roll_log_message_id"), ["message_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_story_roll_log_session_id"), ["session_id"], unique=False)


def downgrade():
    with op.batch_alter_table("story_roll_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_story_roll_log_session_id"))
        batch_op.drop_index(batch_op.f("ix_story_roll_log_message_id"))
    op.drop_table("story_roll_log")

    with op.batch_alter_table("story_image", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_story_image_visual_type"))
        batch_op.drop_index(batch_op.f("ix_story_image_source_message_id"))
        batch_op.drop_index(batch_op.f("ix_story_image_session_id"))
        batch_op.drop_index(batch_op.f("ix_story_image_asset_id"))
    op.drop_table("story_image")

    with op.batch_alter_table("story_session_state", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_story_session_state_session_id"))
    op.drop_table("story_session_state")

    with op.batch_alter_table("story_message", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_story_message_session_id"))
        batch_op.drop_index(batch_op.f("ix_story_message_sender_type"))
        batch_op.drop_index(batch_op.f("ix_story_message_message_type"))
    op.drop_table("story_message")

    with op.batch_alter_table("story_session", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_story_session_story_id"))
        batch_op.drop_index(batch_op.f("ix_story_session_status"))
        batch_op.drop_index(batch_op.f("ix_story_session_project_id"))
        batch_op.drop_index(batch_op.f("ix_story_session_privacy_status"))
        batch_op.drop_index(batch_op.f("ix_story_session_owner_user_id"))
    op.drop_table("story_session")

    with op.batch_alter_table("story", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_story_story_mode"))
        batch_op.drop_index(batch_op.f("ix_story_status"))
        batch_op.drop_index(batch_op.f("ix_story_project_id"))
        batch_op.drop_index(batch_op.f("ix_story_created_by_user_id"))
        batch_op.drop_index(batch_op.f("ix_story_character_id"))
    op.drop_table("story")
