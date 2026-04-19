from ..repositories.scene_repository import SceneRepository
from .scene_character_service import SceneCharacterService
from .story_memory_service import StoryMemoryService


class SceneService:
    def __init__(
        self,
        repository: SceneRepository | None = None,
        scene_character_service: SceneCharacterService | None = None,
        story_memory_service: StoryMemoryService | None = None,
    ):
        self._repo = repository or SceneRepository()
        self._scene_character_service = scene_character_service or SceneCharacterService()
        self._story_memory_service = story_memory_service or StoryMemoryService()

    def _extract_cast_character_ids(self, payload: dict):
        normalized = dict(payload or {})
        cast_character_ids = normalized.pop("cast_character_ids", None)
        return normalized, cast_character_ids

    def list_scenes(self, project_id: int, include_deleted: bool = False):
        return self._repo.list_by_project(project_id, include_deleted=include_deleted)

    def list_scenes_by_chapter(self, chapter_id: int, include_deleted: bool = False):
        return self._repo.list_by_chapter(chapter_id, include_deleted=include_deleted)

    def list_previous_scenes_in_chapter(
        self,
        chapter_id: int,
        sort_order: int,
        scene_id: int,
        *,
        limit: int = 3,
        include_deleted: bool = False,
    ):
        return self._repo.list_previous_in_chapter(
            chapter_id,
            sort_order,
            scene_id,
            limit=limit,
            include_deleted=include_deleted,
        )

    def get_scene(self, scene_id: int, include_deleted: bool = False):
        return self._repo.get(scene_id, include_deleted=include_deleted)

    def create_scene(self, project_id: int, payload: dict):
        payload, cast_character_ids = self._extract_cast_character_ids(payload)
        chapter_id = payload.get("chapter_id")
        if chapter_id is None:
            raise ValueError("chapter_id is required to create a scene")
        scene = self._repo.create(project_id, chapter_id, payload)
        self._scene_character_service.replace_scene_characters(scene.id, cast_character_ids or [])
        self._story_memory_service.sync_scene_memories(scene)
        return scene

    def update_scene(self, scene_id: int, payload: dict):
        payload, cast_character_ids = self._extract_cast_character_ids(payload)
        scene = self._repo.update(scene_id, payload)
        if scene is not None and cast_character_ids is not None:
            self._scene_character_service.replace_scene_characters(scene.id, cast_character_ids)
        if scene is not None and any(
            field in payload for field in ("title", "summary", "narration_text", "dialogue_json", "scene_state_json")
        ):
            self._story_memory_service.sync_scene_memories(scene)
        return scene

    def delete_scene(self, scene_id: int):
        return self._repo.delete(scene_id)

    def fix_scene(self, scene_id: int):
        return self._repo.update(scene_id, {"is_fixed": 1})

    def unfix_scene(self, scene_id: int):
        return self._repo.update(scene_id, {"is_fixed": 0})
