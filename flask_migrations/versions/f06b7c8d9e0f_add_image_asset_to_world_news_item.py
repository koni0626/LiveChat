"""add image asset to world news item

Revision ID: f06b7c8d9e0f
Revises: ff5a6b7c8d9e
Create Date: 2026-04-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f06b7c8d9e0f"
down_revision = "ff5a6b7c8d9e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("world_news_item") as batch_op:
        batch_op.add_column(sa.Column("image_asset_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_world_news_item_image_asset_id"), ["image_asset_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_world_news_item_image_asset_id_asset",
            "asset",
            ["image_asset_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("world_news_item") as batch_op:
        batch_op.drop_constraint("fk_world_news_item_image_asset_id_asset", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_world_news_item_image_asset_id"))
        batch_op.drop_column("image_asset_id")
