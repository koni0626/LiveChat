from ..extensions import db
from ..models.scene_choice import SceneChoice


class SceneChoiceRepository:
    MUTABLE_FIELDS: tuple[str, ...] = (
        "choice_text",
        "next_scene_id",
        "condition_json",
        "result_summary",
        "sort_order",
    )

    def list_by_scene(self, scene_id: int):
        return (
            SceneChoice.query.filter(SceneChoice.scene_id == scene_id)
            .order_by(SceneChoice.sort_order.asc(), SceneChoice.id.asc())
            .all()
        )

    def get(self, choice_id: int):
        return SceneChoice.query.filter(SceneChoice.id == choice_id).first()

    def _next_sort_order(self, scene_id: int) -> int:
        last_choice = (
            SceneChoice.query.filter(SceneChoice.scene_id == scene_id)
            .order_by(SceneChoice.sort_order.desc())
            .first()
        )
        if not last_choice:
            return 1
        return (last_choice.sort_order or 0) + 1

    def create(self, scene_id: int, payload: dict):
        choice = SceneChoice(
            scene_id=scene_id,
            choice_text=payload["choice_text"],
            next_scene_id=payload.get("next_scene_id"),
            condition_json=payload.get("condition_json"),
            result_summary=payload.get("result_summary"),
            sort_order=payload.get("sort_order") or self._next_sort_order(scene_id),
        )
        db.session.add(choice)
        db.session.commit()
        return choice

    def update(self, choice_id: int, payload: dict):
        choice = self.get(choice_id)
        if not choice:
            return None
        for field in self.MUTABLE_FIELDS:
            if field in payload:
                setattr(choice, field, payload[field])
        db.session.commit()
        return choice

    def delete(self, choice_id: int):
        choice = self.get(choice_id)
        if not choice:
            return False
        db.session.delete(choice)
        db.session.commit()
        return True
