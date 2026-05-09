"""add character line tables

Revision ID: 100a1b2c3d4e
Revises: ff5a6b7c8d9e
Create Date: 2026-05-09 13:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "100a1b2c3d4e"
down_revision = "1012b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "character_line_room",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("participant_ids_json", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("last_theme", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_character_line_room_created_by_user_id"), "character_line_room", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_character_line_room_is_default"), "character_line_room", ["is_default"], unique=False)
    op.create_index(op.f("ix_character_line_room_project_id"), "character_line_room", ["project_id"], unique=False)

    op.create_table(
        "character_line_message",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("sender_type", sa.String(length=30), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("generation_batch", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["character_line_room.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_character_line_message_character_id"), "character_line_message", ["character_id"], unique=False)
    op.create_index(op.f("ix_character_line_message_generation_batch"), "character_line_message", ["generation_batch"], unique=False)
    op.create_index(op.f("ix_character_line_message_project_id"), "character_line_message", ["project_id"], unique=False)
    op.create_index(op.f("ix_character_line_message_room_id"), "character_line_message", ["room_id"], unique=False)
    op.create_index(op.f("ix_character_line_message_sender_type"), "character_line_message", ["sender_type"], unique=False)
    op.create_index(op.f("ix_character_line_message_user_id"), "character_line_message", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_character_line_message_user_id"), table_name="character_line_message")
    op.drop_index(op.f("ix_character_line_message_sender_type"), table_name="character_line_message")
    op.drop_index(op.f("ix_character_line_message_room_id"), table_name="character_line_message")
    op.drop_index(op.f("ix_character_line_message_project_id"), table_name="character_line_message")
    op.drop_index(op.f("ix_character_line_message_generation_batch"), table_name="character_line_message")
    op.drop_index(op.f("ix_character_line_message_character_id"), table_name="character_line_message")
    op.drop_table("character_line_message")
    op.drop_index(op.f("ix_character_line_room_project_id"), table_name="character_line_room")
    op.drop_index(op.f("ix_character_line_room_is_default"), table_name="character_line_room")
    op.drop_index(op.f("ix_character_line_room_created_by_user_id"), table_name="character_line_room")
    op.drop_table("character_line_room")
