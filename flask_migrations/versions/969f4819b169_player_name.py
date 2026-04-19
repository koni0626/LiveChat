"""player name

Revision ID: 969f4819b169
Revises: 74ad095217cf
Create Date: 2026-04-19 23:41:32.299007

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '969f4819b169'
down_revision = '74ad095217cf'
branch_labels = None
depends_on = None


def upgrade():
    # no-op: protagonist_name was moved from user_setting to story_outline
    pass


def downgrade():
    # no-op: protagonist_name was moved from user_setting to story_outline
    pass
