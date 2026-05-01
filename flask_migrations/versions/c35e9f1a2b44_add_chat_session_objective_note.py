"""add chat_session_objective_note

Revision ID: c35e9f1a2b44
Revises: b24d8e6f9a31
Create Date: 2026-05-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c35e9f1a2b44"
down_revision = "b24d8e6f9a31"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat_session_objective_note",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="direction_ai"),
        sa.Column("source_ref", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["chat_session.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_session_objective_note_session_id"), "chat_session_objective_note", ["session_id"], unique=False)
    op.create_index(op.f("ix_chat_session_objective_note_character_id"), "chat_session_objective_note", ["character_id"], unique=False)
    op.create_index(op.f("ix_chat_session_objective_note_status"), "chat_session_objective_note", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_chat_session_objective_note_status"), table_name="chat_session_objective_note")
    op.drop_index(op.f("ix_chat_session_objective_note_character_id"), table_name="chat_session_objective_note")
    op.drop_index(op.f("ix_chat_session_objective_note_session_id"), table_name="chat_session_objective_note")
    op.drop_table("chat_session_objective_note")
