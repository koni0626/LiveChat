from datetime import datetime, timedelta

from ..extensions import db
from ..models.letter import Letter
from ..utils import json_util


class LetterRepository:
    def list_for_user(self, user_id: int, *, include_archived: bool = False):
        query = Letter.query.filter(
            Letter.recipient_user_id == user_id,
            Letter.deleted_at.is_(None),
        )
        if not include_archived:
            query = query.filter(Letter.status != "archived")
        return query.order_by(Letter.created_at.desc(), Letter.id.desc()).all()

    def count_unread_for_user(self, user_id: int):
        return Letter.query.filter(
            Letter.recipient_user_id == user_id,
            Letter.status == "unread",
            Letter.deleted_at.is_(None),
        ).count()

    def list_recent_for_guard(
        self,
        *,
        recipient_user_id: int,
        sender_character_id: int,
        room_id: int | None,
        minutes: int,
    ):
        since = datetime.utcnow() - timedelta(minutes=minutes)
        query = Letter.query.filter(
            Letter.recipient_user_id == recipient_user_id,
            Letter.sender_character_id == sender_character_id,
            Letter.created_at >= since,
            Letter.deleted_at.is_(None),
        )
        if room_id is not None:
            query = query.filter(Letter.room_id == room_id)
        return query.order_by(Letter.created_at.desc()).all()

    def find_story_clear_for_session(
        self,
        *,
        story_session_id: int,
        recipient_user_id: int,
        sender_character_id: int,
        project_id: int,
        trigger_type: str = "story_clear",
    ):
        rows = Letter.query.filter(
            Letter.project_id == project_id,
            Letter.recipient_user_id == recipient_user_id,
            Letter.sender_character_id == sender_character_id,
            Letter.trigger_type == trigger_type,
            Letter.deleted_at.is_(None),
        ).order_by(Letter.created_at.desc()).all()
        for row in rows:
            try:
                state = json_util.loads(row.generation_state_json or "{}")
            except Exception:
                state = {}
            if int((state or {}).get("story_session_id") or 0) == int(story_session_id):
                return row
        return None

    def find_for_session_trigger(
        self,
        *,
        session_id: int,
        recipient_user_id: int,
        sender_character_id: int,
        trigger_type: str,
    ):
        return Letter.query.filter(
            Letter.session_id == session_id,
            Letter.recipient_user_id == recipient_user_id,
            Letter.sender_character_id == sender_character_id,
            Letter.trigger_type == trigger_type,
            Letter.deleted_at.is_(None),
        ).order_by(Letter.created_at.desc(), Letter.id.desc()).first()

    def get(self, letter_id: int):
        return Letter.query.get(letter_id)

    def create(self, payload: dict):
        row = Letter(
            project_id=payload["project_id"],
            room_id=payload.get("room_id"),
            session_id=payload.get("session_id"),
            recipient_user_id=payload["recipient_user_id"],
            sender_character_id=payload["sender_character_id"],
            subject=payload["subject"],
            body=payload["body"],
            summary=payload.get("summary"),
            image_asset_id=payload.get("image_asset_id"),
            status=payload.get("status") or "unread",
            trigger_type=payload.get("trigger_type"),
            trigger_reason=payload.get("trigger_reason"),
            generation_state_json=payload.get("generation_state_json"),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def mark_read(self, letter_id: int):
        row = self.get(letter_id)
        if not row:
            return None
        if row.status == "unread":
            row.status = "read"
            row.read_at = datetime.utcnow()
            db.session.commit()
        return row

    def archive(self, letter_id: int):
        row = self.get(letter_id)
        if not row:
            return None
        row.status = "archived"
        db.session.commit()
        return row
