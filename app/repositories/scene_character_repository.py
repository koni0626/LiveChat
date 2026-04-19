from ..extensions import db
from ..models.scene_character import SceneCharacter


class SceneCharacterRepository:
    def list_by_scene(self, scene_id: int):
        return (
            SceneCharacter.query
            .filter(SceneCharacter.scene_id == scene_id)
            .order_by(SceneCharacter.sort_order.asc(), SceneCharacter.id.asc())
            .all()
        )

    def replace_for_scene(self, scene_id: int, character_ids: list[int]):
        SceneCharacter.query.filter(SceneCharacter.scene_id == scene_id).delete()
        rows = [
            SceneCharacter(scene_id=scene_id, character_id=character_id, sort_order=index)
            for index, character_id in enumerate(character_ids, start=1)
        ]
        if rows:
            db.session.add_all(rows)
        db.session.commit()
        return rows
