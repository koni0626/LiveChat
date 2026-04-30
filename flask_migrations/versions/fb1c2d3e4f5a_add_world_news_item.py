"""add world news item

Revision ID: fb1c2d3e4f5a
Revises: fa0b1c2d3e4f
Create Date: 2026-04-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "fb1c2d3e4f5a"
down_revision = "fa0b1c2d3e4f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_news_item",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("related_character_id", sa.Integer(), nullable=True),
        sa.Column("related_location_id", sa.Integer(), nullable=True),
        sa.Column("news_type", sa.String(length=80), nullable=False, server_default="location_news"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("importance", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("source_type", sa.String(length=80), nullable=False, server_default="manual_ai"),
        sa.Column("source_ref_type", sa.String(length=80), nullable=True),
        sa.Column("source_ref_id", sa.Integer(), nullable=True),
        sa.Column("return_url", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="published"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["related_character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["related_location_id"], ["world_location.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_world_news_item_project_id"), "world_news_item", ["project_id"], unique=False)
    op.create_index(op.f("ix_world_news_item_created_by_user_id"), "world_news_item", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_world_news_item_related_character_id"), "world_news_item", ["related_character_id"], unique=False)
    op.create_index(op.f("ix_world_news_item_related_location_id"), "world_news_item", ["related_location_id"], unique=False)
    op.create_index(op.f("ix_world_news_item_news_type"), "world_news_item", ["news_type"], unique=False)
    op.create_index(op.f("ix_world_news_item_source_type"), "world_news_item", ["source_type"], unique=False)
    op.create_index(op.f("ix_world_news_item_status"), "world_news_item", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_world_news_item_status"), table_name="world_news_item")
    op.drop_index(op.f("ix_world_news_item_source_type"), table_name="world_news_item")
    op.drop_index(op.f("ix_world_news_item_news_type"), table_name="world_news_item")
    op.drop_index(op.f("ix_world_news_item_related_location_id"), table_name="world_news_item")
    op.drop_index(op.f("ix_world_news_item_related_character_id"), table_name="world_news_item")
    op.drop_index(op.f("ix_world_news_item_created_by_user_id"), table_name="world_news_item")
    op.drop_index(op.f("ix_world_news_item_project_id"), table_name="world_news_item")
    op.drop_table("world_news_item")
