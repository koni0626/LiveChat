from datetime import datetime

from ..extensions import db
from ..models.world_map_image import WorldMapImage


class WorldMapRepository:
    def list_images(self, project_id: int, include_deleted: bool = False):
        query = WorldMapImage.query.filter(WorldMapImage.project_id == project_id)
        if not include_deleted:
            query = query.filter(WorldMapImage.deleted_at.is_(None))
        return query.order_by(WorldMapImage.is_active.desc(), WorldMapImage.id.desc()).all()

    def get_image(self, image_id: int, include_deleted: bool = False):
        query = WorldMapImage.query.filter(WorldMapImage.id == image_id)
        if not include_deleted:
            query = query.filter(WorldMapImage.deleted_at.is_(None))
        return query.first()

    def get_active_image(self, project_id: int):
        return (
            WorldMapImage.query.filter(
                WorldMapImage.project_id == project_id,
                WorldMapImage.deleted_at.is_(None),
                WorldMapImage.is_active == 1,
            )
            .order_by(WorldMapImage.id.desc())
            .first()
        )

    def create_image(self, project_id: int, payload: dict):
        existing_active = self.get_active_image(project_id)
        image = WorldMapImage(
            project_id=project_id,
            asset_id=payload["asset_id"],
            title=payload.get("title"),
            description=payload.get("description"),
            prompt_text=payload.get("prompt_text"),
            source_type=payload.get("source_type") or "upload",
            quality=payload.get("quality"),
            size=payload.get("size"),
            is_active=1 if not existing_active or payload.get("is_active") else 0,
            created_by_user_id=payload.get("created_by_user_id"),
        )
        if image.is_active:
            self.clear_active(project_id)
        db.session.add(image)
        db.session.commit()
        return image

    def set_active(self, project_id: int, image_id: int):
        image = self.get_image(image_id)
        if not image or image.project_id != project_id:
            return None
        self.clear_active(project_id, commit=False)
        image.is_active = 1
        db.session.commit()
        return image

    def clear_active(self, project_id: int, commit: bool = True):
        WorldMapImage.query.filter(WorldMapImage.project_id == project_id).update({"is_active": 0})
        if commit:
            db.session.commit()

    def delete_image(self, project_id: int, image_id: int):
        image = self.get_image(image_id, include_deleted=True)
        if not image or image.project_id != project_id:
            return False
        if image.deleted_at is not None:
            return True
        was_active = image.is_active == 1
        image.deleted_at = datetime.utcnow()
        image.is_active = 0
        db.session.commit()
        if was_active:
            replacement = self.list_images(project_id)
            if replacement:
                self.set_active(project_id, replacement[0].id)
        return True
