"""add source type to character outfit

Revision ID: ff5a6b7c8d9e
Revises: fe4f5a6b7c8d
Create Date: 2026-04-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "ff5a6b7c8d9e"
down_revision = "fe4f5a6b7c8d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("character_outfit") as batch_op:
        batch_op.add_column(sa.Column("source_type", sa.String(length=50), nullable=False, server_default="outfit"))
        batch_op.create_index(batch_op.f("ix_character_outfit_source_type"), ["source_type"], unique=False)
    op.execute(
        """
        UPDATE character_outfit
        SET source_type = 'character_base'
        WHERE name = '基準画像'
           OR asset_id IN (
                SELECT base_asset_id
                FROM character
                WHERE base_asset_id IS NOT NULL
           )
        """
    )


def downgrade():
    with op.batch_alter_table("character_outfit") as batch_op:
        batch_op.drop_index(batch_op.f("ix_character_outfit_source_type"))
        batch_op.drop_column("source_type")
