from datetime import datetime

from ..extensions import db
from ..models.world_location_service import WorldLocationServiceItem


class WorldLocationServiceRepository:
    MUTABLE_FIELDS = (
        "name",
        "service_type",
        "summary",
        "chat_hook",
        "visual_prompt",
        "status",
        "sort_order",
    )

    def list_by_location(self, location_id: int, include_archived: bool = False, include_deleted: bool = False):
        query = WorldLocationServiceItem.query.filter(WorldLocationServiceItem.location_id == location_id)
        if not include_deleted:
            query = query.filter(WorldLocationServiceItem.deleted_at.is_(None))
        if not include_archived:
            query = query.filter(WorldLocationServiceItem.status == "published")
        return query.order_by(WorldLocationServiceItem.sort_order.asc(), WorldLocationServiceItem.id.asc()).all()

    def get(self, service_id: int, include_deleted: bool = False):
        query = WorldLocationServiceItem.query.filter(WorldLocationServiceItem.id == service_id)
        if not include_deleted:
            query = query.filter(WorldLocationServiceItem.deleted_at.is_(None))
        return query.first()

    def create(self, project_id: int, location_id: int, payload: dict):
        row = WorldLocationServiceItem(
            project_id=project_id,
            location_id=location_id,
            name=payload["name"],
            service_type=payload.get("service_type"),
            summary=payload.get("summary"),
            chat_hook=payload.get("chat_hook"),
            visual_prompt=payload.get("visual_prompt"),
            status=payload.get("status") or "published",
            sort_order=int(payload.get("sort_order") or 0),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def update(self, service_id: int, payload: dict):
        row = self.get(service_id, include_deleted=True)
        if not row or row.deleted_at is not None:
            return None
        for field in self.MUTABLE_FIELDS:
            if field in payload:
                setattr(row, field, payload[field])
        db.session.commit()
        return row

    def archive_missing(self, location_id: int, keep_ids: set[int]):
        rows = self.list_by_location(location_id, include_archived=True)
        for row in rows:
            if row.id not in keep_ids and row.status != "archived":
                row.status = "archived"
        db.session.commit()

    def delete_by_location(self, location_id: int):
        rows = self.list_by_location(location_id, include_archived=True)
        for row in rows:
            if row.deleted_at is None:
                row.deleted_at = datetime.utcnow()
        db.session.commit()
