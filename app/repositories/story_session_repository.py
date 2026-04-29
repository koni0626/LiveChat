from datetime import datetime

from ..extensions import db
from ..models.story_session import StorySession


class StorySessionRepository:
    MUTABLE_FIELDS = (
        "title",
        "status",
        "privacy_status",
        "player_name",
        "active_image_id",
        "story_snapshot_json",
        "settings_json",
    )

    def _base_query(self, include_deleted: bool = False):
        query = StorySession.query
        if not include_deleted:
            query = query.filter(StorySession.deleted_at.is_(None))
        return query

    def list_by_project(self, project_id: int, *, include_deleted: bool = False, owner_user_id: int | None = None):
        query = self._base_query(include_deleted).filter(StorySession.project_id == project_id)
        if owner_user_id is not None:
            query = query.filter(StorySession.owner_user_id == owner_user_id)
        return query.order_by(StorySession.updated_at.desc(), StorySession.id.desc()).all()

    def list_by_story(self, story_id: int, *, include_deleted: bool = False, owner_user_id: int | None = None):
        query = self._base_query(include_deleted).filter(StorySession.story_id == story_id)
        if owner_user_id is not None:
            query = query.filter(StorySession.owner_user_id == owner_user_id)
        return query.order_by(StorySession.updated_at.desc(), StorySession.id.desc()).all()

    def get(self, session_id: int, include_deleted: bool = False):
        return self._base_query(include_deleted).filter(StorySession.id == session_id).first()

    def create(self, payload: dict):
        row = StorySession(
            project_id=payload["project_id"],
            story_id=payload["story_id"],
            owner_user_id=payload["owner_user_id"],
            title=payload.get("title"),
            status=payload.get("status") or "active",
            privacy_status=payload.get("privacy_status") or "private",
            player_name=payload.get("player_name"),
            active_image_id=payload.get("active_image_id"),
            story_snapshot_json=payload.get("story_snapshot_json"),
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
