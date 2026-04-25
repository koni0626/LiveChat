"""add character thumbnail asset

Revision ID: e7a1c3d9f0b2
Revises: d2f4a9b8c6e1
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e7a1c3d9f0b2"
down_revision = "d2f4a9b8c6e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.add_column(sa.Column("thumbnail_asset_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_character_thumbnail_asset_id_asset",
            "asset",
            ["thumbnail_asset_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.drop_constraint("fk_character_thumbnail_asset_id_asset", type_="foreignkey")
        batch_op.drop_column("thumbnail_asset_id")
