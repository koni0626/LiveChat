from __future__ import annotations

import os

from flask import current_app

from ..api import NotFoundError, serialize_datetime
from ..utils import json_util
from .asset_service import AssetService
from .chapter_service import ChapterService
from .character_service import CharacterService
from .glossary_service import GlossaryService
from .project_service import ProjectService
from .scene_choice_service import SceneChoiceService
from .scene_image_service import SceneImageService
from .scene_character_service import SceneCharacterService
from .scene_service import SceneService
from .scene_version_service import SceneVersionService
from .world_service import WorldService


class SceneWorkspaceService:
    def __init__(
        self,
        scene_service: SceneService | None = None,
        scene_choice_service: SceneChoiceService | None = None,
        scene_image_service: SceneImageService | None = None,
        scene_version_service: SceneVersionService | None = None,
        chapter_service: ChapterService | None = None,
        project_service: ProjectService | None = None,
        character_service: CharacterService | None = None,
        glossary_service: GlossaryService | None = None,
        world_service: WorldService | None = None,
        asset_service: AssetService | None = None,
        scene_character_service: SceneCharacterService | None = None,
    ):
        self._scene_service = scene_service or SceneService()
        self._scene_choice_service = scene_choice_service or SceneChoiceService()
        self._scene_image_service = scene_image_service or SceneImageService()
        self._scene_version_service = scene_version_service or SceneVersionService()
        self._chapter_service = chapter_service or ChapterService()
        self._project_service = project_service or ProjectService()
        self._character_service = character_service or CharacterService()
        self._glossary_service = glossary_service or GlossaryService()
        self._world_service = world_service or WorldService()
        self._asset_service = asset_service or AssetService()
        self._scene_character_service = scene_character_service or SceneCharacterService()

    def _load_json(self, value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return json_util.loads(stripped)
        except Exception:
            return value

    def _build_media_url(self, file_path: str | None):
        if not file_path:
            return None
        try:
            storage_root = current_app.config.get("STORAGE_ROOT")
        except RuntimeError:
            storage_root = None
        if not storage_root:
            return None
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        if not normalized_path.startswith(normalized_root):
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"

    def _serialize_asset(self, asset):
        if asset is None:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "file_path": asset.file_path,
            "mime_type": asset.mime_type,
            "file_size": asset.file_size,
            "width": asset.width,
            "height": asset.height,
            "media_url": self._build_media_url(asset.file_path),
        }

    def _serialize_character(self, character):
        asset = self._asset_service.get_asset(character.base_asset_id) if character.base_asset_id else None
        return {
            "id": character.id,
            "name": character.name,
            "role": character.role,
            "first_person": character.first_person,
            "second_person": character.second_person,
            "speech_style": character.speech_style,
            "speech_sample": character.speech_sample,
            "appearance_summary": character.appearance_summary,
            "is_guide": bool(character.is_guide),
            "base_asset": self._serialize_asset(asset),
        }

    def _serialize_choice(self, choice):
        return {
            "id": choice.id,
            "choice_text": choice.choice_text,
            "next_scene_id": choice.next_scene_id,
            "condition_json": self._load_json(choice.condition_json),
            "result_summary": choice.result_summary,
            "sort_order": choice.sort_order,
        }

    def _serialize_scene_image(self, scene_image):
        if scene_image is None:
            return None
        asset = self._asset_service.get_asset(scene_image.asset_id)
        return {
            "id": scene_image.id,
            "asset_id": scene_image.asset_id,
            "image_type": scene_image.image_type,
            "prompt_text": scene_image.prompt_text,
            "state_json": self._load_json(scene_image.state_json),
            "quality": scene_image.quality,
            "size": scene_image.size,
            "is_selected": bool(scene_image.is_selected),
            "created_at": serialize_datetime(getattr(scene_image, "created_at", None)),
            "asset": self._serialize_asset(asset),
        }

    def _serialize_version(self, version):
        return {
            "id": version.id,
            "version_no": version.version_no,
            "source_type": version.source_type,
            "generated_by": version.generated_by,
            "note_text": version.note_text,
            "is_adopted": bool(version.is_adopted),
            "created_at": serialize_datetime(getattr(version, "created_at", None)),
        }

    def _serialize_glossary_term(self, term):
        return {
            "id": term.id,
            "term": term.term,
            "reading": term.reading,
            "description": term.description,
            "category": term.category,
        }

    def _resolve_selected_scene_image(self, scene_id: int):
        images = self._scene_image_service.list_scene_images(scene_id)
        for image in images:
            if image.is_selected:
                return image
        return images[-1] if images else None

    def _serialize_scene(self, scene):
        scene_state = self._load_json(scene.scene_state_json)
        cast_character_ids = self._scene_character_service.list_character_ids(scene.id)
        return {
            "id": scene.id,
            "project_id": scene.project_id,
            "chapter_id": scene.chapter_id,
            "parent_scene_id": scene.parent_scene_id,
            "scene_key": scene.scene_key,
            "title": scene.title,
            "summary": scene.summary,
            "narration_text": scene.narration_text,
            "dialogue_json": self._load_json(scene.dialogue_json),
            "scene_state_json": scene_state,
            "cast_character_ids": cast_character_ids,
            "image_prompt_text": scene.image_prompt_text,
            "active_version_id": scene.active_version_id,
            "sort_order": scene.sort_order,
            "is_fixed": bool(scene.is_fixed),
            "updated_at": serialize_datetime(getattr(scene, "updated_at", None)),
        }

    def _extract_state_value(self, state: dict | list | str | None, *keys):
        if not isinstance(state, dict):
            return None
        for key in keys:
            if state.get(key) not in (None, ""):
                return state.get(key)
        return None

    def get_editor_context(self, scene_id: int):
        scene = self._scene_service.get_scene(scene_id)
        if not scene:
            raise NotFoundError("not_found")

        project = self._project_service.get_project(scene.project_id)
        chapter = self._chapter_service.get_chapter(scene.chapter_id)
        world = self._world_service.get_world(scene.project_id)
        characters = self._character_service.list_characters(scene.project_id)
        glossary_terms = self._glossary_service.list_terms(scene.project_id)
        choices = self._scene_choice_service.list_choices(scene.id)
        selected_image = self._resolve_selected_scene_image(scene.id)
        versions = self._scene_version_service.list_versions(scene.id)

        return {
            "project": {
                "id": project.id if project else scene.project_id,
                "title": project.title if project else None,
                "status": project.status if project else None,
            },
            "chapter": {
                "id": chapter.id,
                "chapter_no": chapter.chapter_no,
                "title": chapter.title,
            } if chapter else None,
            "scene": self._serialize_scene(scene),
            "choices": [self._serialize_choice(choice) for choice in choices],
            "characters": [self._serialize_character(character) for character in characters],
            "world_memo": {
                "name": world.name if world else None,
                "overview": world.overview if world else None,
                "tone": world.tone if world else None,
                "era_description": world.era_description if world else None,
                "technology_level": world.technology_level if world else None,
                "social_structure": world.social_structure if world else None,
                "rules": self._load_json(world.rules_json if world else None),
                "forbidden": self._load_json(world.forbidden_json if world else None),
            },
            "glossary_terms": [self._serialize_glossary_term(term) for term in glossary_terms],
            "selected_image": self._serialize_scene_image(selected_image),
            "recent_versions": [self._serialize_version(version) for version in versions[:5]],
        }

    def get_image_context(self, scene_id: int):
        editor_context = self.get_editor_context(scene_id)
        state = editor_context["scene"]["scene_state_json"]
        return {
            **editor_context,
            "image_generation": {
                "scene_summary": editor_context["scene"]["summary"] or editor_context["scene"]["title"],
                "emotion": self._extract_state_value(state, "emotion", "mood"),
                "place": self._extract_state_value(state, "place", "location"),
                "time_of_day": self._extract_state_value(state, "time_of_day", "time"),
                "prompt_preview": editor_context["scene"]["image_prompt_text"],
            },
        }

    def get_preview(self, scene_id: int):
        scene = self._scene_service.get_scene(scene_id)
        if not scene:
            raise NotFoundError("not_found")

        project = self._project_service.get_project(scene.project_id)
        chapter = self._chapter_service.get_chapter(scene.chapter_id)
        selected_image = self._resolve_selected_scene_image(scene.id)
        choices = self._scene_choice_service.list_choices(scene.id)

        return {
            "project": {
                "id": project.id if project else scene.project_id,
                "title": project.title if project else None,
            },
            "chapter": {
                "id": chapter.id,
                "chapter_no": chapter.chapter_no,
                "title": chapter.title,
            } if chapter else None,
            "scene": {
                "id": scene.id,
                "title": scene.title,
                "summary": scene.summary,
                "narration_text": scene.narration_text,
                "dialogues": self._load_json(scene.dialogue_json),
                "choices": [self._serialize_choice(choice) for choice in choices],
                "image": self._serialize_scene_image(selected_image),
            },
        }
