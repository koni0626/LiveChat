from datetime import datetime

from ..extensions import db
from ..models.chat_session import ChatSession


class ChatSessionRepository:
    MUTABLE_FIELDS = (
        "title",
        "room_id",
        "session_type",
        "status",
        "privacy_status",
        "active_image_id",
        "player_name",
        "settings_json",
        "room_snapshot_json",
    )

    def _base_query(self, include_deleted: bool = False):
        query = ChatSession.query
        if not include_deleted:
            query = query.filter(ChatSession.deleted_at.is_(None))
        return query

    def list_by_project(self, project_id: int, include_deleted: bool = False, owner_user_id: int | None = None):
        query = self._base_query(include_deleted).filter(ChatSession.project_id == project_id)
        if owner_user_id is not None:
            query = query.filter(ChatSession.owner_user_id == owner_user_id)
        return query.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()).all()

    def list_by_room(self, room_id: int, include_deleted: bool = False, owner_user_id: int | None = None):
        query = self._base_query(include_deleted).filter(ChatSession.room_id == room_id)
        if owner_user_id is not None:
            query = query.filter(ChatSession.owner_user_id == owner_user_id)
        return query.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()).all()

    def get(self, session_id: int, include_deleted: bool = False):
        return self._base_query(include_deleted).filter(ChatSession.id == session_id).first()

    def create(self, payload: dict):
        row = ChatSession(
            project_id=payload["project_id"],
            room_id=payload.get("room_id"),
            owner_user_id=payload["owner_user_id"],
            title=payload.get("title"),
            session_type=payload.get("session_type", "live_chat"),
            status=payload.get("status", "active"),
            privacy_status=payload.get("privacy_status", "private"),
            active_image_id=payload.get("active_image_id"),
            player_name=payload.get("player_name"),
            settings_json=payload.get("settings_json"),
            room_snapshot_json=payload.get("room_snapshot_json"),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def update(self, session_id: int, payload: dict):
        row = self.get(session_id, include_deleted=True)
        if not row or row.deleted_at is not None:
            return None
        for field in self.MUTABLE_FIELDS:
            if field in payload:
                setattr(row, field, payload[field])
        db.session.commit()
        return row

    def delete(self, session_id: int):
        row = self.get(session_id, include_deleted=True)
        if not row:
            return False
        if row.deleted_at is not None:
            return True
        row.deleted_at = datetime.utcnow()
        db.session.commit()
        return True
