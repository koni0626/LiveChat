"""add default outfit to story

Revision ID: fe4f5a6b7c8d
Revises: fd3e4f5a6b7c
Create Date: 2026-04-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "fe4f5a6b7c8d"
down_revision = "fd3e4f5a6b7c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("story") as batch_op:
        batch_op.add_column(sa.Column("default_outfit_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_story_default_outfit_id"), ["default_outfit_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_story_default_outfit_id_character_outfit",
            "character_outfit",
            ["default_outfit_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("story") as batch_op:
        batch_op.drop_constraint("fk_story_default_outfit_id_character_outfit", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_story_default_outfit_id"))
        batch_op.drop_column("default_outfit_id")
