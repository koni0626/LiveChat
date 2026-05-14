"""add learning student to live chat room

Revision ID: fg6b7c8d9e0f
Revises: ff5a6b7c8d9e
Create Date: 2026-05-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "fg6b7c8d9e0f"
down_revision = "ff5a6b7c8d9e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("live_chat_room") as batch_op:
        batch_op.add_column(sa.Column("student_character_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("student_default_outfit_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_live_chat_room_student_character_id"), ["student_character_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_live_chat_room_student_default_outfit_id"), ["student_default_outfit_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_live_chat_room_student_character_id_character",
            "character",
            ["student_character_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_live_chat_room_student_default_outfit_id_character_outfit",
            "character_outfit",
            ["student_default_outfit_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("live_chat_room") as batch_op:
        batch_op.drop_constraint("fk_live_chat_room_student_default_outfit_id_character_outfit", type_="foreignkey")
        batch_op.drop_constraint("fk_live_chat_room_student_character_id_character", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_live_chat_room_student_default_outfit_id"))
        batch_op.drop_index(batch_op.f("ix_live_chat_room_student_character_id"))
        batch_op.drop_column("student_default_outfit_id")
        batch_op.drop_column("student_character_id")
