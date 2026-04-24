"""character memory fields

Revision ID: 1f3d5f0e8a21
Revises: e7cca3af1c56
Create Date: 2026-04-25 11:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "1f3d5f0e8a21"
down_revision = "e7cca3af1c56"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.add_column(sa.Column("memory_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("favorite_items_json", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("character", schema=None) as batch_op:
        batch_op.drop_column("favorite_items_json")
        batch_op.drop_column("memory_notes")
