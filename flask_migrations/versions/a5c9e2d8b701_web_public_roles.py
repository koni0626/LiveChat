"""web public roles

Revision ID: a5c9e2d8b701
Revises: 4d8b2c1a9f61
Create Date: 2026-04-25 18:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a5c9e2d8b701"
down_revision = "4d8b2c1a9f61"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.add_column(sa.Column("role", sa.String(length=50), nullable=False, server_default="user"))

    with op.batch_alter_table("project", schema=None) as batch_op:
        batch_op.add_column(sa.Column("visibility", sa.String(length=50), nullable=False, server_default="private"))
        batch_op.add_column(sa.Column("chat_enabled", sa.Integer(), nullable=False, server_default="1"))

    with op.batch_alter_table("chat_session", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("privacy_status", sa.String(length=50), nullable=False, server_default="private"))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE chat_session
            SET owner_user_id = (
                SELECT project.owner_user_id
                FROM project
                WHERE project.id = chat_session.project_id
            )
            WHERE owner_user_id IS NULL
            """
        )
    )

    with op.batch_alter_table("chat_session", schema=None) as batch_op:
        batch_op.alter_column("owner_user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_index(batch_op.f("ix_chat_session_owner_user_id"), ["owner_user_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_chat_session_owner_user_id_user"),
            "user",
            ["owner_user_id"],
            ["id"],
        )


def downgrade():
    with op.batch_alter_table("chat_session", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_chat_session_owner_user_id_user"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_chat_session_owner_user_id"))
        batch_op.drop_column("privacy_status")
        batch_op.drop_column("owner_user_id")

    with op.batch_alter_table("project", schema=None) as batch_op:
        batch_op.drop_column("chat_enabled")
        batch_op.drop_column("visibility")

    with op.batch_alter_table("user", schema=None) as batch_op:
        batch_op.drop_column("role")
