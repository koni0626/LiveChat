"""drop unused legacy tables

Revision ID: 929d9f8aebbb
Revises: d6a7b8c9e012
Create Date: 2026-04-26 17:39:12.925235

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '929d9f8aebbb'
down_revision = 'd6a7b8c9e012'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('ending_condition')
    op.drop_table('glossary_term')


def downgrade():
    op.create_table('glossary_term',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('world_id', sa.INTEGER(), nullable=False),
    sa.Column('term', sa.VARCHAR(length=255), nullable=False),
    sa.Column('reading', sa.VARCHAR(length=255), nullable=True),
    sa.Column('description', sa.TEXT(), nullable=True),
    sa.Column('category', sa.VARCHAR(length=100), nullable=True),
    sa.Column('sort_order', sa.INTEGER(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.ForeignKeyConstraint(['world_id'], ['world.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ending_condition',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('project_id', sa.INTEGER(), nullable=False),
    sa.Column('ending_type', sa.VARCHAR(length=50), nullable=False),
    sa.Column('name', sa.VARCHAR(length=255), nullable=False),
    sa.Column('condition_text', sa.TEXT(), nullable=True),
    sa.Column('condition_json', sa.TEXT(), nullable=True),
    sa.Column('priority', sa.INTEGER(), nullable=False),
    sa.Column('updated_at', sa.DATETIME(), nullable=False),
    sa.Column('created_at', sa.DATETIME(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
