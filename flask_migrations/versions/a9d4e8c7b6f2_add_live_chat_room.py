"""add live chat room

Revision ID: a9d4e8c7b6f2
Revises: f4c2b8a1d9e0
Create Date: 2026-04-26 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
import json
from datetime import datetime


revision = "a9d4e8c7b6f2"
down_revision = "f4c2b8a1d9e0"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "live_chat_room" not in set(inspector.get_table_names()):
        op.create_table(
            "live_chat_room",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("created_by_user_id", sa.Integer(), nullable=False),
            sa.Column("character_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("conversation_objective", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["character_id"], ["character.id"]),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["user.id"]),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing("live_chat_room", "ix_live_chat_room_character_id", ["character_id"])
    _create_index_if_missing("live_chat_room", "ix_live_chat_room_created_by_user_id", ["created_by_user_id"])
    _create_index_if_missing("live_chat_room", "ix_live_chat_room_project_id", ["project_id"])
    _create_index_if_missing("live_chat_room", "ix_live_chat_room_status", ["status"])
    _create_index_if_missing("live_chat_room", "ix_live_chat_room_project_status", ["project_id", "status"])

    chat_session_columns = _column_names("chat_session")
    should_add_room_id = "room_id" not in chat_session_columns
    should_add_snapshot = "room_snapshot_json" not in chat_session_columns
    if should_add_room_id or should_add_snapshot:
        with op.batch_alter_table("chat_session", schema=None) as batch_op:
            if should_add_room_id:
                batch_op.add_column(sa.Column("room_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key("fk_chat_session_room_id_live_chat_room", "live_chat_room", ["room_id"], ["id"])
            if should_add_snapshot:
                batch_op.add_column(sa.Column("room_snapshot_json", sa.Text(), nullable=True))

    _create_index_if_missing("chat_session", "ix_chat_session_room_id", ["room_id"])
    _create_index_if_missing("chat_session", "ix_chat_session_room_owner", ["room_id", "owner_user_id"])
    _create_index_if_missing("chat_session", "ix_chat_session_project_owner", ["project_id", "owner_user_id"])

    _create_rooms_for_existing_sessions()


def _column_names(table_name):
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def _index_names(table_name):
    inspector = sa.inspect(op.get_bind())
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _create_index_if_missing(table_name, index_name, columns):
    if index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns, unique=False)


def _load_json(value):
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_character_id(settings_json):
    selected = settings_json.get("selected_character_ids")
    if isinstance(selected, list) and selected:
        try:
            return int(selected[0])
        except (TypeError, ValueError):
            return None
    try:
        return int(settings_json.get("selected_character_id") or 0) or None
    except (TypeError, ValueError):
        return None


def _create_rooms_for_existing_sessions():
    if "room_id" not in _column_names("chat_session"):
        return
    conn = op.get_bind()
    sessions = conn.execute(
        sa.text(
            """
            SELECT id, project_id, owner_user_id, title, settings_json, room_id, created_at, updated_at
            FROM chat_session
            WHERE room_id IS NULL
            """
        )
    ).mappings().all()
    if not sessions:
        return

    for session in sessions:
        settings_json = _load_json(session.get("settings_json"))
        character_id = _extract_character_id(settings_json)
        if not character_id:
            character_id = conn.execute(
                sa.text(
                    """
                    SELECT id
                    FROM character
                    WHERE project_id = :project_id AND deleted_at IS NULL
                    ORDER BY id ASC
                    LIMIT 1
                    """
                ),
                {"project_id": session["project_id"]},
            ).scalar()
        if not character_id:
            continue

        project_owner_id = conn.execute(
            sa.text("SELECT owner_user_id FROM project WHERE id = :project_id"),
            {"project_id": session["project_id"]},
        ).scalar()
        character_name = conn.execute(
            sa.text("SELECT name FROM character WHERE id = :character_id"),
            {"character_id": character_id},
        ).scalar()
        objective = str(
            settings_json.get("conversation_objective")
            or settings_json.get("session_objective")
            or "このルームの会話目的を設定してください。"
        ).strip()
        now = datetime.utcnow()
        title = str(session.get("title") or "").strip() or f"{character_name or 'キャラクター'}との会話"
        room_title = f"{title} ルーム"
        result = conn.execute(
            sa.text(
                """
                INSERT INTO live_chat_room (
                    project_id, created_by_user_id, character_id, title, description,
                    conversation_objective, status, sort_order, created_at, updated_at, deleted_at
                )
                VALUES (
                    :project_id, :created_by_user_id, :character_id, :title, :description,
                    :conversation_objective, :status, :sort_order, :created_at, :updated_at, NULL
                )
                """
            ),
            {
                "project_id": session["project_id"],
                "created_by_user_id": project_owner_id or session["owner_user_id"],
                "character_id": character_id,
                "title": room_title,
                "description": "既存セッションから自動作成されたルームです。",
                "conversation_objective": objective,
                "status": "published",
                "sort_order": 0,
                "created_at": session.get("created_at") or now,
                "updated_at": session.get("updated_at") or now,
            },
        )
        room_id = result.lastrowid
        snapshot = {
            "room_id": room_id,
            "room_title": room_title,
            "conversation_objective": objective,
            "character_id": character_id,
            "character_name": character_name,
            "status": "published",
            "version_updated_at": (session.get("updated_at") or now).isoformat()
            if hasattr(session.get("updated_at") or now, "isoformat")
            else str(session.get("updated_at") or now),
        }
        conn.execute(
            sa.text(
                """
                UPDATE chat_session
                SET room_id = :room_id, room_snapshot_json = :room_snapshot_json
                WHERE id = :session_id
                """
            ),
            {
                "room_id": room_id,
                "room_snapshot_json": json.dumps(snapshot, ensure_ascii=False),
                "session_id": session["id"],
            },
        )


def downgrade():
    chat_session_columns = _column_names("chat_session")
    if "room_id" in chat_session_columns or "room_snapshot_json" in chat_session_columns:
        existing_indexes = _index_names("chat_session")
        with op.batch_alter_table("chat_session", schema=None) as batch_op:
            if "ix_chat_session_project_owner" in existing_indexes:
                batch_op.drop_index("ix_chat_session_project_owner")
            if "ix_chat_session_room_owner" in existing_indexes:
                batch_op.drop_index("ix_chat_session_room_owner")
            if "ix_chat_session_room_id" in existing_indexes:
                batch_op.drop_index("ix_chat_session_room_id")
            if "room_snapshot_json" in chat_session_columns:
                batch_op.drop_column("room_snapshot_json")
            if "room_id" in chat_session_columns:
                batch_op.drop_column("room_id")

    if "live_chat_room" in set(sa.inspect(op.get_bind()).get_table_names()):
        existing_indexes = _index_names("live_chat_room")
        for index_name in (
            "ix_live_chat_room_project_status",
            "ix_live_chat_room_status",
            "ix_live_chat_room_project_id",
            "ix_live_chat_room_created_by_user_id",
            "ix_live_chat_room_character_id",
        ):
            if index_name in existing_indexes:
                op.drop_index(index_name, table_name="live_chat_room")
        op.drop_table("live_chat_room")
