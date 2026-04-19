from __future__ import annotations

from ..api import NotFoundError, serialize_datetime
from .character_service import CharacterService
from .project_service import ProjectService
from .scene_choice_service import SceneChoiceService
from .scene_image_service import SceneImageService
from .scene_service import SceneService


class ProjectOverviewService:
    def __init__(
        self,
        project_service: ProjectService | None = None,
        character_service: CharacterService | None = None,
        scene_service: SceneService | None = None,
        scene_choice_service: SceneChoiceService | None = None,
        scene_image_service: SceneImageService | None = None,
    ):
        self._project_service = project_service or ProjectService()
        self._character_service = character_service or CharacterService()
        self._scene_service = scene_service or SceneService()
        self._scene_choice_service = scene_choice_service or SceneChoiceService()
        self._scene_image_service = scene_image_service or SceneImageService()

    def _serialize_recent_scene(self, scene):
        return {
            "id": scene.id,
            "chapter_id": scene.chapter_id,
            "scene_key": scene.scene_key,
            "title": scene.title,
            "summary": scene.summary,
            "sort_order": scene.sort_order,
            "is_fixed": bool(scene.is_fixed),
            "updated_at": serialize_datetime(getattr(scene, "updated_at", None)),
        }

    def _has_selected_image(self, scene_id: int) -> bool:
        images = self._scene_image_service.list_scene_images(scene_id)
        return any(bool(item.is_selected) for item in images)

    def get_overview(self, project_id: int):
        project = self._project_service.get_project(project_id)
        if not project:
            raise NotFoundError("not_found")

        characters = self._character_service.list_characters(project_id)
        scenes = self._scene_service.list_scenes(project_id)
        branch_count = 0
        ungenerated_image_count = 0

        for scene in scenes:
            branch_count += len(self._scene_choice_service.list_choices(scene.id))
            if not self._has_selected_image(scene.id):
                ungenerated_image_count += 1

        recent_scenes = sorted(
            scenes,
            key=lambda item: (
                getattr(item, "updated_at", None) is not None,
                getattr(item, "updated_at", None),
                item.id,
            ),
            reverse=True,
        )[:5]

        return {
            "project": {
                "id": project.id,
                "title": project.title,
                "summary": project.summary,
                "status": project.status,
                "genre": project.genre,
                "updated_at": serialize_datetime(getattr(project, "updated_at", None)),
            },
            "stats": {
                "character_count": len(characters),
                "scene_count": len(scenes),
                "branch_count": branch_count,
                "ungenerated_image_count": ungenerated_image_count,
            },
            "recent_scenes": [self._serialize_recent_scene(scene) for scene in recent_scenes],
        }
