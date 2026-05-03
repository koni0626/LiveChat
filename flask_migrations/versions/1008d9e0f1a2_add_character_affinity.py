"""add character affinity

Revision ID: 1008d9e0f1a2
Revises: 1007c8d9e0f1
Create Date: 2026-05-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "1008d9e0f1a2"
down_revision = "1007c8d9e0f1"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("character_user_memory")}
    with op.batch_alter_table("character_user_memory") as batch_op:
        if "affinity_score" not in columns:
            batch_op.add_column(sa.Column("affinity_score", sa.Integer(), nullable=False, server_default="0"))
        if "affinity_label" not in columns:
            batch_op.add_column(sa.Column("affinity_label", sa.String(length=80), nullable=True))
        if "affinity_notes" not in columns:
            batch_op.add_column(sa.Column("affinity_notes", sa.Text(), nullable=True))
        if "physical_closeness_level" not in columns:
            batch_op.add_column(sa.Column("physical_closeness_level", sa.Integer(), nullable=False, server_default="0"))


def downgrade():
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("character_user_memory")}
    with op.batch_alter_table("character_user_memory") as batch_op:
        if "physical_closeness_level" in columns:
            batch_op.drop_column("physical_closeness_level")
        if "affinity_notes" in columns:
            batch_op.drop_column("affinity_notes")
        if "affinity_label" in columns:
            batch_op.drop_column("affinity_label")
        if "affinity_score" in columns:
            batch_op.drop_column("affinity_score")
