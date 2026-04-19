from ..repositories.scene_character_repository import SceneCharacterRepository


class SceneCharacterService:
    def __init__(self, repository: SceneCharacterRepository | None = None):
        self._repo = repository or SceneCharacterRepository()

    def _normalize_character_ids(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            value = [value]
        normalized = []
        seen = set()
        for item in value:
            try:
                character_id = int(item)
            except (TypeError, ValueError):
                continue
            if character_id <= 0 or character_id in seen:
                continue
            seen.add(character_id)
            normalized.append(character_id)
        return normalized

    def list_scene_characters(self, scene_id: int):
        return self._repo.list_by_scene(scene_id)

    def list_character_ids(self, scene_id: int):
        return [row.character_id for row in self._repo.list_by_scene(scene_id)]

    def replace_scene_characters(self, scene_id: int, character_ids):
        normalized = self._normalize_character_ids(character_ids)
        return self._repo.replace_for_scene(scene_id, normalized)
