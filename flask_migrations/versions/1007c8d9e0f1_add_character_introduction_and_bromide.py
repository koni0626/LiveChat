"""add character introduction and bromide

Revision ID: 1007c8d9e0f1
Revises: 1006b7c8d9e0
Create Date: 2026-05-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "1007c8d9e0f1"
down_revision = "1006b7c8d9e0"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("character")}
    with op.batch_alter_table("character") as batch_op:
        if "introduction_text" not in columns:
            batch_op.add_column(sa.Column("introduction_text", sa.Text(), nullable=True))
        if "bromide_asset_id" not in columns:
            batch_op.add_column(sa.Column("bromide_asset_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_character_bromide_asset_id_asset",
                "asset",
                ["bromide_asset_id"],
                ["id"],
            )


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("character")}
    with op.batch_alter_table("character") as batch_op:
        if "bromide_asset_id" in columns:
            batch_op.drop_constraint("fk_character_bromide_asset_id_asset", type_="foreignkey")
            batch_op.drop_column("bromide_asset_id")
        if "introduction_text" in columns:
            batch_op.drop_column("introduction_text")
