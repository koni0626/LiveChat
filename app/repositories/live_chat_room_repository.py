from datetime import datetime

from ..extensions import db
from ..models.live_chat_room import LiveChatRoom


class LiveChatRoomRepository:
    MUTABLE_FIELDS = (
        "title",
        "description",
        "conversation_objective",
        "proxy_player_objective",
        "proxy_player_gender",
        "proxy_player_speech_style",
        "character_id",
        "default_outfit_id",
        "status",
        "sort_order",
    )

    def _base_query(self, include_deleted: bool = False):
        query = LiveChatRoom.query
        if not include_deleted:
            query = query.filter(LiveChatRoom.deleted_at.is_(None))
        return query

    def list_by_project(
        self,
        project_id: int,
        *,
        include_deleted: bool = False,
        status: str | None = None,
    ):
        query = self._base_query(include_deleted).filter(LiveChatRoom.project_id == project_id)
        if status:
            query = query.filter(LiveChatRoom.status == status)
        return query.order_by(LiveChatRoom.sort_order.asc(), LiveChatRoom.updated_at.desc(), LiveChatRoom.id.desc()).all()

    def get(self, room_id: int, include_deleted: bool = False):
        return self._base_query(include_deleted).filter(LiveChatRoom.id == room_id).first()

    def create(self, payload: dict):
        row = LiveChatRoom(
            project_id=payload["project_id"],
            created_by_user_id=payload["created_by_user_id"],
            character_id=payload["character_id"],
            default_outfit_id=payload.get("default_outfit_id"),
            title=payload["title"],
            description=payload.get("description"),
            conversation_objective=payload["conversation_objective"],
            proxy_player_objective=payload.get("proxy_player_objective"),
            proxy_player_gender=payload.get("proxy_player_gender"),
            proxy_player_speech_style=payload.get("proxy_player_speech_style"),
            status=payload.get("status") or "draft",
            sort_order=payload.get("sort_order") or 0,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def update(self, room_id: int, payload: dict):
        row = self.get(room_id, include_deleted=True)
        if not row or row.deleted_at is not None:
            return None
        for field in self.MUTABLE_FIELDS:
            if field in payload:
                setattr(row, field, payload[field])
        db.session.commit()
        return row

    def delete(self, room_id: int):
        row = self.get(room_id, include_deleted=True)
        if not row:
            return False
        if row.deleted_at is not None:
            return True
        row.deleted_at = datetime.utcnow()
        db.session.commit()
        return True
