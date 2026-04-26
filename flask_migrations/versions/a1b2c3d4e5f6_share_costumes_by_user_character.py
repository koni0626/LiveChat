"""share costumes by user character

Revision ID: a1b2c3d4e5f6
Revises: 929d9f8aebbb
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "929d9f8aebbb"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("session_image", schema=None) as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("character_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("linked_from_image_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_session_image_owner_user_id"), ["owner_user_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_session_image_character_id"), ["character_id"], unique=False)
        batch_op.create_foreign_key("fk_session_image_owner_user_id_user", "user", ["owner_user_id"], ["id"])
        batch_op.create_foreign_key("fk_session_image_character_id_character", "character", ["character_id"], ["id"])
        batch_op.create_foreign_key(
            "fk_session_image_linked_from_image_id_session_image",
            "session_image",
            ["linked_from_image_id"],
            ["id"],
        )

    op.execute(
        """
        UPDATE session_image
        SET owner_user_id = (
            SELECT chat_session.owner_user_id
            FROM chat_session
            WHERE chat_session.id = session_image.session_id
        )
        WHERE image_type IN ('costume_initial', 'costume_reference')
        """
    )
    op.execute(
        """
        UPDATE session_image
        SET character_id = (
            SELECT live_chat_room.character_id
            FROM chat_session
            JOIN live_chat_room ON live_chat_room.id = chat_session.room_id
            WHERE chat_session.id = session_image.session_id
        )
        WHERE image_type IN ('costume_initial', 'costume_reference')
        """
    )


def downgrade():
    with op.batch_alter_table("session_image", schema=None) as batch_op:
        batch_op.drop_constraint("fk_session_image_linked_from_image_id_session_image", type_="foreignkey")
        batch_op.drop_constraint("fk_session_image_character_id_character", type_="foreignkey")
        batch_op.drop_constraint("fk_session_image_owner_user_id_user", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_session_image_character_id"))
        batch_op.drop_index(batch_op.f("ix_session_image_owner_user_id"))
        batch_op.drop_column("linked_from_image_id")
        batch_op.drop_column("character_id")
        batch_op.drop_column("owner_user_id")
