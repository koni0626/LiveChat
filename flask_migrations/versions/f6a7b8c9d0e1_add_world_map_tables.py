"""add world map tables

Revision ID: f6a7b8c9d0e1
Revises: e3f4a5b6c7d8
Create Date: 2026-04-29 14:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "world_location",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("location_type", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_character_id", sa.Integer(), nullable=True),
        sa.Column("image_asset_id", sa.Integer(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="published"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["image_asset_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["owner_character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_world_location_project_id", "world_location", ["project_id"])
    op.create_index("ix_world_location_owner_character_id", "world_location", ["owner_character_id"])

    op.create_table(
        "world_map_image",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("prompt_text", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False, server_default="upload"),
        sa.Column("quality", sa.String(length=50), nullable=True),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_world_map_image_project_id", "world_map_image", ["project_id"])


def downgrade():
    op.drop_index("ix_world_map_image_project_id", table_name="world_map_image")
    op.drop_table("world_map_image")
    op.drop_index("ix_world_location_owner_character_id", table_name="world_location")
    op.drop_index("ix_world_location_project_id", table_name="world_location")
    op.drop_table("world_location")
