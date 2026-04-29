"""add outing session

Revision ID: fa0b1c2d3e4f
Revises: f9d0e1f2a3b4
Create Date: 2026-04-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "fa0b1c2d3e4f"
down_revision = "f9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "outing_session",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("mood", sa.String(length=100), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("memory_title", sa.String(length=255), nullable=True),
        sa.Column("memory_summary", sa.Text(), nullable=True),
        sa.Column("state_json", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["world_location.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_outing_session_project_id"), "outing_session", ["project_id"], unique=False)
    op.create_index(op.f("ix_outing_session_user_id"), "outing_session", ["user_id"], unique=False)
    op.create_index(op.f("ix_outing_session_character_id"), "outing_session", ["character_id"], unique=False)
    op.create_index(op.f("ix_outing_session_location_id"), "outing_session", ["location_id"], unique=False)
    op.create_index(op.f("ix_outing_session_status"), "outing_session", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_outing_session_status"), table_name="outing_session")
    op.drop_index(op.f("ix_outing_session_location_id"), table_name="outing_session")
    op.drop_index(op.f("ix_outing_session_character_id"), table_name="outing_session")
    op.drop_index(op.f("ix_outing_session_user_id"), table_name="outing_session")
    op.drop_index(op.f("ix_outing_session_project_id"), table_name="outing_session")
    op.drop_table("outing_session")
