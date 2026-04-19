from sqlalchemy import func

from ..extensions import db
from ..models.scene import Scene
from ..models.scene_version import SceneVersion


class SceneVersionRepository:
    MUTABLE_FIELDS: tuple[str, ...] = (
        "source_type",
        "generated_by",
        "narration_text",
        "dialogue_json",
        "choice_json",
        "scene_state_json",
        "image_prompt_text",
        "note_text",
    )

    def _next_version_no(self, scene_id: int) -> int:
        max_version = (
            db.session.query(func.coalesce(func.max(SceneVersion.version_no), 0))
            .filter(SceneVersion.scene_id == scene_id)
            .scalar()
        )
        return (max_version or 0) + 1
    def list_by_scene(self, scene_id: int):
        return (
            SceneVersion.query
            .filter(SceneVersion.scene_id == scene_id)
            .order_by(SceneVersion.version_no.desc(), SceneVersion.id.desc())
            .all()
        )

    def get(self, version_id: int):
        return SceneVersion.query.filter(SceneVersion.id == version_id).first()

    def create(self, scene_id: int, payload: dict):
        version_no = payload.get("version_no") or self._next_version_no(scene_id)
        version = SceneVersion(
            scene_id=scene_id,
            version_no=version_no,
            source_type=payload.get("source_type", "manual"),
            generated_by=payload.get("generated_by"),
            narration_text=payload.get("narration_text"),
            dialogue_json=payload.get("dialogue_json"),
            choice_json=payload.get("choice_json"),
            scene_state_json=payload.get("scene_state_json"),
            image_prompt_text=payload.get("image_prompt_text"),
            note_text=payload.get("note_text"),
            is_adopted=1 if payload.get("is_adopted") else 0,
        )
        db.session.add(version)
        db.session.commit()
        return version

    def update(self, version_id: int, payload: dict):
        version = self.get(version_id)
        if not version:
            return None
        for field in self.MUTABLE_FIELDS:
            if field in payload:
                setattr(version, field, payload[field])
        if "is_adopted" in payload:
            version.is_adopted = 1 if payload["is_adopted"] else 0
        db.session.commit()
        return version

    def adopt(self, scene_id: int, version_id: int):
        version = (
            SceneVersion.query
            .filter(SceneVersion.id == version_id, SceneVersion.scene_id == scene_id)
            .first()
        )
        if not version:
            return None

        SceneVersion.query.filter(
            SceneVersion.scene_id == scene_id, SceneVersion.is_adopted == 1
        ).update({"is_adopted": 0}, synchronize_session=False)

        version.is_adopted = 1

        scene = Scene.query.filter(Scene.id == scene_id).first()
        if scene:
            scene.active_version_id = version.id

        db.session.commit()
        return version

    def delete(self, version_id: int):
        version = self.get(version_id)
        if not version:
            return False
        db.session.delete(version)
        db.session.commit()
        return True
