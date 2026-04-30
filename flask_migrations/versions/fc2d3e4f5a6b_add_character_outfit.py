"""add character outfit

Revision ID: fc2d3e4f5a6b
Revises: fb1c2d3e4f5a
Create Date: 2026-04-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "fc2d3e4f5a6b"
down_revision = "fb1c2d3e4f5a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "character_outfit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("asset_id", sa.Integer(), nullable=False),
        sa.Column("thumbnail_asset_id", sa.Integer(), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=True),
        sa.Column("usage_scene", sa.String(length=80), nullable=True),
        sa.Column("season", sa.String(length=80), nullable=True),
        sa.Column("mood", sa.String(length=80), nullable=True),
        sa.Column("color_notes", sa.Text(), nullable=True),
        sa.Column("fixed_parts", sa.Text(), nullable=True),
        sa.Column("allowed_changes", sa.Text(), nullable=True),
        sa.Column("ng_rules", sa.Text(), nullable=True),
        sa.Column("prompt_notes", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
        sa.ForeignKeyConstraint(["thumbnail_asset_id"], ["asset.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_character_outfit_project_id"), "character_outfit", ["project_id"], unique=False)
    op.create_index(op.f("ix_character_outfit_character_id"), "character_outfit", ["character_id"], unique=False)
    op.create_index(op.f("ix_character_outfit_asset_id"), "character_outfit", ["asset_id"], unique=False)
    op.create_index(op.f("ix_character_outfit_thumbnail_asset_id"), "character_outfit", ["thumbnail_asset_id"], unique=False)
    op.create_index(op.f("ix_character_outfit_usage_scene"), "character_outfit", ["usage_scene"], unique=False)
    op.create_index(op.f("ix_character_outfit_season"), "character_outfit", ["season"], unique=False)
    op.create_index(op.f("ix_character_outfit_mood"), "character_outfit", ["mood"], unique=False)
    op.create_index(op.f("ix_character_outfit_is_default"), "character_outfit", ["is_default"], unique=False)
    op.create_index(op.f("ix_character_outfit_status"), "character_outfit", ["status"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_character_outfit_status"), table_name="character_outfit")
    op.drop_index(op.f("ix_character_outfit_is_default"), table_name="character_outfit")
    op.drop_index(op.f("ix_character_outfit_mood"), table_name="character_outfit")
    op.drop_index(op.f("ix_character_outfit_season"), table_name="character_outfit")
    op.drop_index(op.f("ix_character_outfit_usage_scene"), table_name="character_outfit")
    op.drop_index(op.f("ix_character_outfit_thumbnail_asset_id"), table_name="character_outfit")
    op.drop_index(op.f("ix_character_outfit_asset_id"), table_name="character_outfit")
    op.drop_index(op.f("ix_character_outfit_character_id"), table_name="character_outfit")
    op.drop_index(op.f("ix_character_outfit_project_id"), table_name="character_outfit")
    op.drop_table("character_outfit")
