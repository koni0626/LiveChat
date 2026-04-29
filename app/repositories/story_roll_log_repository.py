from ..extensions import db
from ..models.story_roll_log import StoryRollLog


class StoryRollLogRepository:
    def list_by_session(self, session_id: int):
        return (
            StoryRollLog.query.filter(StoryRollLog.session_id == session_id)
            .order_by(StoryRollLog.created_at.asc(), StoryRollLog.id.asc())
            .all()
        )

    def create(self, payload: dict):
        row = StoryRollLog(
            session_id=payload["session_id"],
            message_id=payload.get("message_id"),
            formula=payload["formula"],
            dice_json=payload["dice_json"],
            modifier=payload.get("modifier") or 0,
            total=payload["total"],
            target=payload.get("target"),
            outcome=payload.get("outcome"),
            reason=payload.get("reason"),
            metadata_json=payload.get("metadata_json"),
        )
        db.session.add(row)
        db.session.commit()
        return row
