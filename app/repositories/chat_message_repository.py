from sqlalchemy import func

from ..extensions import db
from ..models.chat_message import ChatMessage


class ChatMessageRepository:
    def list_by_session(self, session_id: int):
        return (
            ChatMessage.query.filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.order_no.asc(), ChatMessage.id.asc())
            .all()
        )

    def get(self, message_id: int):
        return ChatMessage.query.get(message_id)

    def get_max_order_no(self, session_id: int) -> int:
        value = (
            db.session.query(func.max(ChatMessage.order_no))
            .filter(ChatMessage.session_id == session_id)
            .scalar()
        )
        return int(value or 0)

    def create(self, payload: dict):
        row = ChatMessage(
            session_id=payload["session_id"],
            sender_type=payload["sender_type"],
            speaker_name=payload.get("speaker_name"),
            message_text=payload["message_text"],
            order_no=payload["order_no"],
            message_role=payload.get("message_role"),
            state_snapshot_json=payload.get("state_snapshot_json"),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def delete(self, message_id: int):
        row = self.get(message_id)
        if not row:
            return None
        db.session.delete(row)
        db.session.commit()
        return row
