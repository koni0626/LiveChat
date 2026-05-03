"""add user points

Revision ID: 1010f1a2b3c4
Revises: 1009e0f1a2b3
Create Date: 2026-05-03 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "1010f1a2b3c4"
down_revision = "1009e0f1a2b3"
branch_labels = None
depends_on = None


def _columns(table_name: str) -> set[str]:
    inspector = inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    bind = op.get_bind()
    user_columns = _columns("user")
    if "points_balance" not in user_columns:
        with op.batch_alter_table("user") as batch_op:
            batch_op.add_column(
                sa.Column("points_balance", sa.Integer(), nullable=False, server_default="3000")
            )

    inspector = inspect(bind)
    if "point_transaction" not in inspector.get_table_names():
        op.create_table(
            "point_transaction",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("action_type", sa.String(length=100), nullable=False),
            sa.Column("points_delta", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="success"),
            sa.Column("session_id", sa.Integer(), nullable=True),
            sa.Column("message_id", sa.Integer(), nullable=True),
            sa.Column("image_id", sa.Integer(), nullable=True),
            sa.Column("detail_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.ForeignKeyConstraint(["session_id"], ["chat_session.id"]),
            sa.ForeignKeyConstraint(["message_id"], ["chat_message.id"]),
            sa.ForeignKeyConstraint(["image_id"], ["session_image.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in {
        "ix_point_transaction_user_id": ["user_id"],
        "ix_point_transaction_project_id": ["project_id"],
        "ix_point_transaction_action_type": ["action_type"],
        "ix_point_transaction_status": ["status"],
        "ix_point_transaction_session_id": ["session_id"],
        "ix_point_transaction_message_id": ["message_id"],
        "ix_point_transaction_image_id": ["image_id"],
    }.items():
        if index_name not in {idx["name"] for idx in inspect(bind).get_indexes("point_transaction")}:
            op.create_index(index_name, "point_transaction", columns, unique=False)


def downgrade():
    inspector = inspect(op.get_bind())
    if "point_transaction" in inspector.get_table_names():
        for index_name in [
            "ix_point_transaction_image_id",
            "ix_point_transaction_message_id",
            "ix_point_transaction_session_id",
            "ix_point_transaction_status",
            "ix_point_transaction_action_type",
            "ix_point_transaction_project_id",
            "ix_point_transaction_user_id",
        ]:
            if index_name in {idx["name"] for idx in inspector.get_indexes("point_transaction")}:
                op.drop_index(index_name, table_name="point_transaction")
        op.drop_table("point_transaction")
    if "points_balance" in _columns("user"):
        with op.batch_alter_table("user") as batch_op:
            batch_op.drop_column("points_balance")
