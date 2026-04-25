"""drop character guide and image rules

Revision ID: c8e4d1f0a2b3
Revises: b7f2c93e1a44
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c8e4d1f0a2b3"
down_revision = "b7f2c93e1a44"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table("character_image_rule")
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.drop_column("is_guide")


def downgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.add_column(sa.Column("is_guide", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "character_image_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("hair_rule", sa.Text(), nullable=True),
        sa.Column("face_rule", sa.Text(), nullable=True),
        sa.Column("ear_rule", sa.Text(), nullable=True),
        sa.Column("accessory_rule", sa.Text(), nullable=True),
        sa.Column("outfit_rule", sa.Text(), nullable=True),
        sa.Column("style_rule", sa.Text(), nullable=True),
        sa.Column("negative_rule", sa.Text(), nullable=True),
        sa.Column("default_quality", sa.String(length=50), nullable=False, server_default="low"),
        sa.Column("default_size", sa.String(length=50), nullable=False, server_default="1024x1024"),
        sa.Column("prompt_prefix", sa.Text(), nullable=True),
        sa.Column("prompt_suffix", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
        sa.UniqueConstraint("character_id"),
    )
