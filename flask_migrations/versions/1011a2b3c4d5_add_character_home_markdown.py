"""add character home markdown

Revision ID: 1011a2b3c4d5
Revises: 1010f1a2b3c4
Create Date: 2026-05-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "1011a2b3c4d5"
down_revision = "1010f1a2b3c4"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    if "home_markdown" not in _columns("character"):
        with op.batch_alter_table("character") as batch_op:
            batch_op.add_column(sa.Column("home_markdown", sa.Text(), nullable=True))


def downgrade():
    if "home_markdown" in _columns("character"):
        with op.batch_alter_table("character") as batch_op:
            batch_op.drop_column("home_markdown")
