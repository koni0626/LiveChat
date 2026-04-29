from datetime import datetime

from ..extensions import db
from ..models.world_location import WorldLocation


class WorldLocationRepository:
    MUTABLE_FIELDS = (
        "name",
        "region",
        "location_type",
        "tags_json",
        "description",
        "image_prompt",
        "owner_character_id",
        "image_asset_id",
        "source_type",
        "source_note",
        "status",
        "sort_order",
    )

    def list_by_project(self, project_id: int, include_deleted: bool = False):
        query = WorldLocation.query.filter(WorldLocation.project_id == project_id)
        if not include_deleted:
            query = query.filter(WorldLocation.deleted_at.is_(None))
        return query.order_by(WorldLocation.sort_order.asc(), WorldLocation.id.desc()).all()

    def get(self, location_id: int, include_deleted: bool = False):
        query = WorldLocation.query.filter(WorldLocation.id == location_id)
        if not include_deleted:
            query = query.filter(WorldLocation.deleted_at.is_(None))
        return query.first()

    def create(self, project_id: int, payload: dict):
        location = WorldLocation(
            project_id=project_id,
            name=payload["name"],
            region=payload.get("region"),
            location_type=payload.get("location_type"),
            tags_json=payload.get("tags_json"),
            description=payload.get("description"),
            image_prompt=payload.get("image_prompt"),
            owner_character_id=payload.get("owner_character_id"),
            image_asset_id=payload.get("image_asset_id"),
            source_type=payload.get("source_type") or "manual",
            source_note=payload.get("source_note"),
            status=payload.get("status") or "published",
            sort_order=int(payload.get("sort_order") or 0),
        )
        db.session.add(location)
        db.session.commit()
        return location

    def update(self, location_id: int, payload: dict):
        location = self.get(location_id, include_deleted=True)
        if not location or location.deleted_at is not None:
            return None
        for field in self.MUTABLE_FIELDS:
            if field in payload:
                setattr(location, field, payload[field])
        db.session.commit()
        return location

    def delete(self, location_id: int):
        location = self.get(location_id, include_deleted=True)
        if not location:
            return False
        if location.deleted_at is not None:
            return True
        location.deleted_at = datetime.utcnow()
        db.session.commit()
        return True
