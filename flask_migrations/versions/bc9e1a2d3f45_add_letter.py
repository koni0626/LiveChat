"""add letter

Revision ID: bc9e1a2d3f45
Revises: a9d4e8c7b6f2
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "bc9e1a2d3f45"
down_revision = "a9d4e8c7b6f2"
branch_labels = None
depends_on = None


def _table_names():
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table_name):
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(table_name, index_name, columns):
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns, unique=False)


def upgrade():
    if "letter" not in _table_names():
        op.create_table(
            "letter",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=True),
            sa.Column("session_id", sa.Integer(), nullable=True),
            sa.Column("recipient_user_id", sa.Integer(), nullable=False),
            sa.Column("sender_character_id", sa.Integer(), nullable=False),
            sa.Column("subject", sa.String(length=255), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("image_asset_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("trigger_type", sa.String(length=50), nullable=True),
            sa.Column("trigger_reason", sa.Text(), nullable=True),
            sa.Column("generation_state_json", sa.Text(), nullable=True),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["image_asset_id"], ["asset.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["room_id"], ["live_chat_room.id"]),
            sa.ForeignKeyConstraint(["sender_character_id"], ["character.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["chat_session.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing("letter", "ix_letter_project_id", ["project_id"])
    _create_index_if_missing("letter", "ix_letter_recipient_user_id", ["recipient_user_id"])
    _create_index_if_missing("letter", "ix_letter_room_id", ["room_id"])
    _create_index_if_missing("letter", "ix_letter_sender_character_id", ["sender_character_id"])
    _create_index_if_missing("letter", "ix_letter_session_id", ["session_id"])
    _create_index_if_missing("letter", "ix_letter_status", ["status"])
    _create_index_if_missing("letter", "ix_letter_recipient_status", ["recipient_user_id", "status"])


def downgrade():
    if "letter" in _table_names():
        for index_name in (
            "ix_letter_recipient_status",
            "ix_letter_status",
            "ix_letter_session_id",
            "ix_letter_sender_character_id",
            "ix_letter_room_id",
            "ix_letter_recipient_user_id",
            "ix_letter_project_id",
        ):
            if index_name in _index_names("letter"):
                op.drop_index(index_name, table_name="letter")
        op.drop_table("letter")
