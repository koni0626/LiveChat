"""add character art style

Revision ID: d6a7b8c9e012
Revises: bc9e1a2d3f45
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d6a7b8c9e012"
down_revision = "bc9e1a2d3f45"
branch_labels = None
depends_on = None


def _column_names(table_name):
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade():
    if "art_style" not in _column_names("character"):
        with op.batch_alter_table("character", schema=None) as batch_op:
            batch_op.add_column(sa.Column("art_style", sa.Text(), nullable=True))


def downgrade():
    if "art_style" in _column_names("character"):
        with op.batch_alter_table("character", schema=None) as batch_op:
            batch_op.drop_column("art_style")
