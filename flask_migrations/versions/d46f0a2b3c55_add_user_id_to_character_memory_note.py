"""add user_id to character_memory_note

Revision ID: d46f0a2b3c55
Revises: c35e9f1a2b44
Create Date: 2026-05-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "d46f0a2b3c55"
down_revision = "c35e9f1a2b44"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("character_memory_note") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_character_memory_note_user_id_user",
            "user",
            ["user_id"],
            ["id"],
        )
        batch_op.create_index("ix_character_memory_note_user_id", ["user_id"], unique=False)


def downgrade():
    with op.batch_alter_table("character_memory_note") as batch_op:
        batch_op.drop_index("ix_character_memory_note_user_id")
        batch_op.drop_constraint("fk_character_memory_note_user_id_user", type_="foreignkey")
        batch_op.drop_column("user_id")
