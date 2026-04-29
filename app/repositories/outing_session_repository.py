from datetime import datetime

from ..extensions import db
from ..models.outing_session import OutingSession


class OutingSessionRepository:
    def list_by_project_user(self, project_id: int, user_id: int, *, limit: int = 30):
        return (
            OutingSession.query.filter(
                OutingSession.project_id == project_id,
                OutingSession.user_id == user_id,
                OutingSession.deleted_at.is_(None),
            )
            .order_by(OutingSession.updated_at.desc(), OutingSession.id.desc())
            .limit(limit)
            .all()
        )

    def get(self, outing_id: int):
        return OutingSession.query.filter(
            OutingSession.id == outing_id,
            OutingSession.deleted_at.is_(None),
        ).first()

    def create(self, payload: dict):
        row = OutingSession(
            project_id=payload["project_id"],
            user_id=payload["user_id"],
            character_id=payload["character_id"],
            location_id=payload["location_id"],
            title=payload["title"],
            status=payload.get("status") or "active",
            current_step=int(payload.get("current_step") or 0),
            max_steps=int(payload.get("max_steps") or 3),
            mood=payload.get("mood"),
            summary=payload.get("summary"),
            memory_title=payload.get("memory_title"),
            memory_summary=payload.get("memory_summary"),
            state_json=payload.get("state_json"),
            completed_at=payload.get("completed_at"),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def update(self, outing_id: int, payload: dict):
        row = self.get(outing_id)
        if not row:
            return None
        for field in (
            "title",
            "status",
            "current_step",
            "max_steps",
            "mood",
            "summary",
            "memory_title",
            "memory_summary",
            "state_json",
            "completed_at",
        ):
            if field in payload:
                setattr(row, field, payload[field])
        db.session.commit()
        return row

    def delete(self, outing_id: int):
        row = self.get(outing_id)
        if not row:
            return False
        row.deleted_at = datetime.utcnow()
        db.session.commit()
        return True
