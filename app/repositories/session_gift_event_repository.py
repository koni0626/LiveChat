from ..extensions import db
from ..models.session_gift_event import SessionGiftEvent


class SessionGiftEventRepository:
    def list_by_session(self, session_id: int):
        return (
            SessionGiftEvent.query.filter(SessionGiftEvent.session_id == session_id)
            .order_by(SessionGiftEvent.id.asc())
            .all()
        )

    def get(self, gift_event_id: int):
        return SessionGiftEvent.query.get(gift_event_id)

    def create(self, payload: dict):
        row = SessionGiftEvent(
            session_id=payload["session_id"],
            actor_type=payload["actor_type"],
            character_id=payload.get("character_id"),
            asset_id=payload["asset_id"],
            gift_direction=payload["gift_direction"],
            recognized_label=payload.get("recognized_label"),
            recognized_tags_json=payload.get("recognized_tags_json"),
            reaction_summary=payload.get("reaction_summary"),
            evaluation_delta=int(payload.get("evaluation_delta") or 0),
        )
        db.session.add(row)
        db.session.commit()
        return row
