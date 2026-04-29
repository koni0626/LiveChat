from sqlalchemy import func

from ..extensions import db
from ..models.story_message import StoryMessage


class StoryMessageRepository:
    def list_by_session(self, session_id: int, include_deleted: bool = False):
        query = StoryMessage.query.filter(StoryMessage.session_id == session_id)
        if not include_deleted:
            query = query.filter(StoryMessage.deleted_at.is_(None))
        return query.order_by(StoryMessage.order_no.asc(), StoryMessage.id.asc()).all()

    def get(self, message_id: int, include_deleted: bool = False):
        query = StoryMessage.query.filter(StoryMessage.id == message_id)
        if not include_deleted:
            query = query.filter(StoryMessage.deleted_at.is_(None))
        return query.first()

    def get_max_order_no(self, session_id: int) -> int:
        value = db.session.query(func.max(StoryMessage.order_no)).filter(StoryMessage.session_id == session_id).scalar()
        return int(value or 0)

    def create(self, payload: dict):
        row = StoryMessage(
            session_id=payload["session_id"],
            sender_type=payload["sender_type"],
            speaker_name=payload.get("speaker_name"),
            message_text=payload["message_text"],
            message_type=payload.get("message_type") or "dialogue",
            order_no=payload["order_no"],
            metadata_json=payload.get("metadata_json"),
        )
        db.session.add(row)
        db.session.commit()
        return row
