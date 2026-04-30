from datetime import datetime

from ..extensions import db
from ..models.world_news_item import WorldNewsItem


class WorldNewsRepository:
    def list_by_project(self, project_id: int, *, status: str = "published", limit: int = 50):
        query = WorldNewsItem.query.filter(
            WorldNewsItem.project_id == project_id,
            WorldNewsItem.deleted_at.is_(None),
        )
        if status:
            query = query.filter(WorldNewsItem.status == status)
        return query.order_by(WorldNewsItem.created_at.desc(), WorldNewsItem.id.desc()).limit(limit).all()

    def get(self, news_id: int):
        return WorldNewsItem.query.filter(
            WorldNewsItem.id == news_id,
            WorldNewsItem.deleted_at.is_(None),
        ).first()

    def find_by_source(self, *, project_id: int, source_type: str, source_ref_type: str, source_ref_id: int):
        return WorldNewsItem.query.filter(
            WorldNewsItem.project_id == project_id,
            WorldNewsItem.source_type == source_type,
            WorldNewsItem.source_ref_type == source_ref_type,
            WorldNewsItem.source_ref_id == source_ref_id,
            WorldNewsItem.deleted_at.is_(None),
        ).first()

    def create(self, payload: dict):
        row = WorldNewsItem(
            project_id=payload["project_id"],
            created_by_user_id=payload.get("created_by_user_id"),
            related_character_id=payload.get("related_character_id"),
            related_location_id=payload.get("related_location_id"),
            news_type=payload.get("news_type") or "location_news",
            title=payload["title"],
            body=payload["body"],
            summary=payload.get("summary"),
            importance=int(payload.get("importance") or 3),
            source_type=payload.get("source_type") or "manual_ai",
            source_ref_type=payload.get("source_ref_type"),
            source_ref_id=payload.get("source_ref_id"),
            return_url=payload.get("return_url"),
            status=payload.get("status") or "published",
            metadata_json=payload.get("metadata_json"),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def delete(self, news_id: int):
        row = self.get(news_id)
        if not row:
            return False
        row.deleted_at = datetime.utcnow()
        db.session.commit()
        return True
