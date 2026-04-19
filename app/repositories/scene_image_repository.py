from ..extensions import db
from ..models.scene_image import SceneImage


class SceneImageRepository:
    def list_by_scene(self, scene_id: int):
        return (
            SceneImage.query.filter_by(scene_id=scene_id)
            .order_by(SceneImage.id)
            .all()
        )

    def get(self, scene_image_id: int):
        return SceneImage.query.get(scene_image_id)

    def create_for_scene(self, scene_id: int, payload: dict):
        scene_image = SceneImage(
            scene_id=scene_id,
            scene_version_id=payload.get("scene_version_id"),
            asset_id=payload["asset_id"],
            image_type=payload["image_type"],
            generation_job_id=payload.get("generation_job_id"),
            prompt_text=payload.get("prompt_text"),
            state_json=payload.get("state_json"),
            quality=payload["quality"],
            size=payload["size"],
            is_selected=payload.get("is_selected", 0),
        )
        db.session.add(scene_image)
        db.session.commit()
        return scene_image

    def select(self, scene_image_id: int):
        scene_image = self.get(scene_image_id)
        if not scene_image:
            return None
        SceneImage.query.filter_by(scene_id=scene_image.scene_id).update(
            {"is_selected": 0}
        )
        scene_image.is_selected = 1
        db.session.commit()
        return scene_image

    def regenerate(self, scene_image_id: int, payload: dict | None = None):
        source_image = self.get(scene_image_id)
        if not source_image:
            return None
        payload = payload or {}
        scene_image = SceneImage(
            scene_id=source_image.scene_id,
            scene_version_id=payload.get("scene_version_id", source_image.scene_version_id),
            asset_id=payload.get("asset_id", source_image.asset_id),
            image_type=payload.get("image_type", source_image.image_type),
            generation_job_id=payload.get("generation_job_id"),
            prompt_text=payload.get("prompt_text", source_image.prompt_text),
            state_json=payload.get("state_json"),
            quality=payload.get("quality", source_image.quality),
            size=payload.get("size", source_image.size),
            is_selected=0,
        )
        db.session.add(scene_image)
        db.session.commit()
        return scene_image
