from datetime import datetime

from ..extensions import db
from ..models.chat_session import ChatSession


class ChatSessionRepository:
    MUTABLE_FIELDS = (
        "title",
        "session_type",
        "status",
        "active_image_id",
        "player_name",
        "settings_json",
    )

    def _base_query(self, include_deleted: bool = False):
        query = ChatSession.query
        if not include_deleted:
            query = query.filter(ChatSession.deleted_at.is_(None))
        return query

    def list_by_project(self, project_id: int, include_deleted: bool = False):
        return (
            self._base_query(include_deleted)
            .filter(ChatSession.project_id == project_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
            .all()
        )

    def get(self, session_id: int, include_deleted: bool = False):
        return self._base_query(include_deleted).filter(ChatSession.id == session_id).first()

    def create(self, payload: dict):
        row = ChatSession(
            project_id=payload["project_id"],
            title=payload.get("title"),
            session_type=payload.get("session_type", "live_chat"),
            status=payload.get("status", "active"),
            active_image_id=payload.get("active_image_id"),
            player_name=payload.get("player_name"),
            settings_json=payload.get("settings_json"),
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
