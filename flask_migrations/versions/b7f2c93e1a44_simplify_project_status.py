"""simplify project status

Revision ID: b7f2c93e1a44
Revises: a5c9e2d8b701
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7f2c93e1a44"
down_revision = "a5c9e2d8b701"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE project
            SET status = CASE
                WHEN status = 'published' THEN 'published'
                WHEN status = 'active' THEN 'published'
                ELSE 'draft'
            END,
            visibility = CASE
                WHEN status IN ('published', 'active') THEN 'published'
                ELSE 'private'
            END,
            chat_enabled = 1
            """
        )
    )


def downgrade():
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE project
            SET status = CASE
                WHEN status = 'published' THEN 'active'
                ELSE 'draft'
            END
            """
        )
    )
