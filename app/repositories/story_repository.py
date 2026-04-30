from datetime import datetime

from ..extensions import db
from ..models.story import Story


class StoryRepository:
    MUTABLE_FIELDS = (
        "title",
        "description",
        "status",
        "story_mode",
        "character_id",
        "default_outfit_id",
        "config_markdown",
        "config_json",
        "initial_state_json",
        "style_reference_asset_id",
        "main_character_reference_asset_id",
        "sort_order",
    )

    def _base_query(self, include_deleted: bool = False):
        query = Story.query
        if not include_deleted:
            query = query.filter(Story.deleted_at.is_(None))
        return query

    def list_by_project(self, project_id: int, *, include_deleted: bool = False, status: str | None = None):
        query = self._base_query(include_deleted).filter(Story.project_id == project_id)
        if status:
            query = query.filter(Story.status == status)
        return query.order_by(Story.sort_order.asc(), Story.updated_at.desc(), Story.id.desc()).all()

    def get(self, story_id: int, include_deleted: bool = False):
        return self._base_query(include_deleted).filter(Story.id == story_id).first()

    def create(self, payload: dict):
        row = Story(
            project_id=payload["project_id"],
            character_id=payload["character_id"],
            default_outfit_id=payload.get("default_outfit_id"),
            created_by_user_id=payload["created_by_user_id"],
            title=payload["title"],
            description=payload.get("description"),
            status=payload.get("status") or "draft",
            story_mode=payload.get("story_mode") or "free_chat",
            config_markdown=payload.get("config_markdown"),
            config_json=payload.get("config_json"),
            initial_state_json=payload.get("initial_state_json"),
            style_reference_asset_id=payload.get("style_reference_asset_id"),
            main_character_reference_asset_id=payload.get("main_character_reference_asset_id"),
            sort_order=payload.get("sort_order") or 0,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def update(self, story_id: int, payload: dict):
        row = self.get(story_id, include_deleted=True)
        if not row or row.deleted_at is not None:
            return None
        for field in self.MUTABLE_FIELDS:
            if field in payload:
                setattr(row, field, payload[field])
        db.session.commit()
        return row

    def delete(self, story_id: int):
        row = self.get(story_id, include_deleted=True)
        if not row:
            return False
        if row.deleted_at is not None:
            return True
        row.deleted_at = datetime.utcnow()
        db.session.commit()
        return True
