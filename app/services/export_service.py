import os
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from flask import current_app, render_template

from ..utils import json_util
from .asset_service import AssetService
from .chapter_service import ChapterService
from .character_service import CharacterService
from .project_service import ProjectService
from .scene_choice_service import SceneChoiceService
from .scene_image_service import SceneImageService
from .scene_service import SceneService
from .story_outline_service import StoryOutlineService
from .world_service import WorldService
from ..repositories.export_job_repository import ExportJobRepository


class ExportService:
    VALID_STATUSES = {"queued", "running", "success", "failed"}
    SUPPORTED_EXPORT_TYPES = {"json", "html", "text"}

    def __init__(
        self,
        repository: ExportJobRepository | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        story_outline_service: StoryOutlineService | None = None,
        chapter_service: ChapterService | None = None,
        character_service: CharacterService | None = None,
        scene_service: SceneService | None = None,
        scene_choice_service: SceneChoiceService | None = None,
        scene_image_service: SceneImageService | None = None,
        asset_service: AssetService | None = None,
    ):
        self._repo = repository or ExportJobRepository()
        self._project_service = project_service or ProjectService()
        self._world_service = world_service or WorldService()
        self._story_outline_service = story_outline_service or StoryOutlineService()
        self._chapter_service = chapter_service or ChapterService()
        self._character_service = character_service or CharacterService()
        self._scene_service = scene_service or SceneService()
        self._scene_choice_service = scene_choice_service or SceneChoiceService()
        self._scene_image_service = scene_image_service or SceneImageService()
        self._asset_service = asset_service or AssetService()

    def _normalize_status(self, status: str):
        if not status:
            raise ValueError("status is required")
        if status not in self.VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(self.VALID_STATUSES)}")
        return status

    def _normalize_export_type(self, export_type: str):
        value = str(export_type or "").strip().lower()
        if not value:
            raise ValueError("export_type is required")
        if value not in self.SUPPORTED_EXPORT_TYPES:
            raise ValueError(f"export_type must be one of {sorted(self.SUPPORTED_EXPORT_TYPES)}")
        return value

    def _resolve_options_json(self, payload: dict) -> str | None:
        if "options_json" in payload and payload.get("options_json") is not None:
            return payload.get("options_json")
        if "include_images" in payload:
            return json_util.dumps({"include_images": bool(payload.get("include_images"))})
        return None

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

    def _get_storage_root(self) -> str:
        return current_app.config.get("STORAGE_ROOT")

    def _get_export_root(self, project_id: int) -> Path:
        return Path(self._get_storage_root()) / "projects" / str(project_id) / "exports"

    def _build_bundle_paths(self, project_id: int, export_type: str) -> tuple[Path, Path]:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        base_name = f"{export_type}_export_{timestamp}"
        bundle_dir = self._get_export_root(project_id) / base_name
        zip_path = self._get_export_root(project_id) / f"{base_name}.zip"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        return bundle_dir, zip_path

    def _select_scene_image(self, scene_id: int):
        images = self._scene_image_service.list_scene_images(scene_id)
        for image in images:
            if image.is_selected:
                return image
        return images[-1] if images else None

    def _copy_asset_to_bundle(self, asset, asset_dir: Path) -> str | None:
        if not asset or not getattr(asset, "file_path", None):
            return None
        source_path = Path(asset.file_path)
        if not source_path.exists():
            return None
        asset_dir.mkdir(parents=True, exist_ok=True)
        target_name = source_path.name
        target_path = asset_dir / target_name
        if not target_path.exists():
            shutil.copy2(source_path, target_path)
        return f"assets/{target_name}".replace("\\", "/")

    def _build_export_data(self, project_id: int, bundle_dir: Path | None = None) -> dict:
        project = self._project_service.get_project(project_id)
        if not project:
            raise ValueError("project not found")

        world = self._world_service.get_world(project_id)
        story_outline = self._story_outline_service.get_outline(project_id)
        chapters = self._chapter_service.list_chapters(project_id)
        characters = self._character_service.list_characters(project_id)
        scenes = self._scene_service.list_scenes(project_id)

        asset_dir = (bundle_dir / "assets") if bundle_dir is not None else None

        chapter_payload = []
        for chapter in chapters:
            chapter_payload.append(
                {
                    "id": chapter.id,
                    "chapter_no": chapter.chapter_no,
                    "title": chapter.title,
                    "summary": chapter.summary,
                    "objective": chapter.objective,
                    "sort_order": chapter.sort_order,
                }
            )

        character_payload = []
        for character in characters:
            base_asset = self._asset_service.get_asset(character.base_asset_id) if character.base_asset_id else None
            base_asset_path = self._copy_asset_to_bundle(base_asset, asset_dir) if asset_dir else None
            character_payload.append(
                {
                    "id": character.id,
                    "name": character.name,
                    "role": character.role,
                    "first_person": character.first_person,
                    "second_person": character.second_person,
                    "personality": character.personality,
                    "speech_style": character.speech_style,
                    "speech_sample": character.speech_sample,
                    "appearance_summary": character.appearance_summary,
                    "is_guide": bool(character.is_guide),
                    "base_asset_path": base_asset_path,
                }
            )

        scene_payload = []
        for scene in scenes:
            selected_image = self._select_scene_image(scene.id)
            selected_asset = self._asset_service.get_asset(selected_image.asset_id) if selected_image else None
            image_path = self._copy_asset_to_bundle(selected_asset, asset_dir) if asset_dir else None
            choices = self._scene_choice_service.list_choices(scene.id)
            scene_payload.append(
                {
                    "id": scene.id,
                    "chapter_id": scene.chapter_id,
                    "scene_key": scene.scene_key,
                    "title": scene.title,
                    "summary": scene.summary,
                    "narration_text": scene.narration_text,
                    "dialogues": self._load_json(scene.dialogue_json) or [],
                    "scene_state": self._load_json(scene.scene_state_json),
                    "image_prompt_text": scene.image_prompt_text,
                    "sort_order": scene.sort_order,
                    "is_fixed": bool(scene.is_fixed),
                    "image_path": image_path,
                    "choices": [
                        {
                            "id": choice.id,
                            "choice_text": choice.choice_text,
                            "next_scene_id": choice.next_scene_id,
                            "condition_json": self._load_json(choice.condition_json),
                            "result_summary": choice.result_summary,
                            "sort_order": choice.sort_order,
                        }
                        for choice in choices
                    ],
                }
            )

        scene_payload.sort(key=lambda item: (item["chapter_id"] or 0, item["sort_order"] or 0, item["id"]))
        start_scene_id = scene_payload[0]["id"] if scene_payload else None

        return {
            "meta": {
                "exported_at": datetime.utcnow().isoformat(),
                "project_id": project.id,
                "start_scene_id": start_scene_id,
            },
            "project": {
                "id": project.id,
                "title": project.title,
                "genre": project.genre,
                "summary": project.summary,
                "status": project.status,
                "project_type": project.project_type,
            },
            "world": (
                {
                    "name": world.name,
                    "era_description": world.era_description,
                    "technology_level": world.technology_level,
                    "social_structure": world.social_structure,
                    "tone": world.tone,
                    "overview": world.overview,
                    "rules": self._load_json(world.rules_json),
                    "forbidden": self._load_json(world.forbidden_json),
                }
                if world
                else None
            ),
            "story_outline": (
                {
                    "premise": story_outline.premise,
                    "protagonist_position": story_outline.protagonist_position,
                    "main_goal": story_outline.main_goal,
                    "branching_policy": story_outline.branching_policy,
                    "ending_policy": story_outline.ending_policy,
                    "outline_text": story_outline.outline_text,
                    "outline_json": self._load_json(story_outline.outline_json),
                }
                if story_outline
                else None
            ),
            "chapters": chapter_payload,
            "characters": character_payload,
            "scenes": scene_payload,
        }

    def _build_text_export(self, export_data: dict) -> str:
        lines = [export_data["project"]["title"] or "Untitled", ""]
        for scene in export_data.get("scenes", []):
            lines.append(f"## {scene.get('title') or '無題のシーン'}")
            if scene.get("summary"):
                lines.append(scene["summary"])
                lines.append("")
            if scene.get("narration_text"):
                lines.append(scene["narration_text"])
                lines.append("")
            for dialogue in scene.get("dialogues") or []:
                if isinstance(dialogue, dict):
                    speaker = dialogue.get("speaker") or dialogue.get("speaker_name") or ""
                    text = dialogue.get("text") or dialogue.get("dialogue_text") or ""
                    if speaker:
                        lines.append(f"{speaker}: {text}")
                    elif text:
                        lines.append(text)
                elif isinstance(dialogue, str):
                    lines.append(dialogue)
            if scene.get("choices"):
                lines.append("")
                lines.append("選択肢:")
                for choice in scene["choices"]:
                    lines.append(f"- {choice.get('choice_text')}")
            lines.append("")
        return "\n".join(lines).strip() + "\n"

    def _write_json_export(self, bundle_dir: Path, export_data: dict) -> Path:
        output_path = bundle_dir / "project-export.json"
        output_path.write_text(json_util.dumps(export_data, indent=2), encoding="utf-8")
        return output_path

    def _write_text_export(self, bundle_dir: Path, export_data: dict) -> Path:
        output_path = bundle_dir / "project-export.txt"
        output_path.write_text(self._build_text_export(export_data), encoding="utf-8")
        return output_path

    def _write_html_export(self, bundle_dir: Path, export_data: dict) -> Path:
        html = render_template("exports/runtime.html", export_data_json=json_util.dumps(export_data))
        output_path = bundle_dir / "index.html"
        output_path.write_text(html, encoding="utf-8")
        return output_path

    def _zip_directory(self, source_dir: Path, zip_path: Path) -> None:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for file_path in source_dir.rglob("*"):
                if file_path.is_file():
                    archive.write(file_path, file_path.relative_to(source_dir))

    def _register_export_asset(self, project_id: int, zip_path: Path, export_type: str) -> int:
        asset = self._asset_service.create_asset(
            project_id,
            {
                "asset_type": "export_bundle",
                "file_name": zip_path.name,
                "file_path": str(zip_path),
                "mime_type": "application/zip",
                "file_size": zip_path.stat().st_size,
                "metadata_json": json_util.dumps({"export_type": export_type}),
            },
        )
        return asset.id

    def _process_export(self, export_job):
        export_type = self._normalize_export_type(export_job.export_type)
        bundle_dir, zip_path = self._build_bundle_paths(export_job.project_id, export_type)
        export_data = self._build_export_data(export_job.project_id, bundle_dir if export_type == "html" else None)

        if export_type == "json":
            self._write_json_export(bundle_dir, export_data)
        elif export_type == "text":
            self._write_text_export(bundle_dir, export_data)
        elif export_type == "html":
            self._write_html_export(bundle_dir, export_data)

        self._zip_directory(bundle_dir, zip_path)
        asset_id = self._register_export_asset(export_job.project_id, zip_path, export_type)
        self.mark_finished(export_job.id, asset_id=asset_id)
        return self.get_export(export_job.id)

    def list_exports(self, project_id: int, limit: int | None = None):
        return self._repo.list_by_project(project_id, limit=limit)

    def create_export(self, project_id: int, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        export_type = self._normalize_export_type(payload.get("export_type"))
        options_json = self._resolve_options_json(payload)
        normalized = {
            "export_type": export_type,
            "asset_id": payload.get("asset_id"),
            "options_json": options_json,
            "status": self._normalize_status(payload.get("status") or "queued"),
            "started_at": payload.get("started_at"),
            "finished_at": payload.get("finished_at"),
            "error_message": payload.get("error_message"),
        }
        export_job = self._repo.create(project_id, normalized)
        self.mark_started(export_job.id)
        try:
            return self._process_export(export_job)
        except Exception as exc:
            self.mark_failed(export_job.id, str(exc))
            raise

    def get_export(self, export_job_id: int):
        return self._repo.get_by_id(export_job_id)

    def queue_export(
        self,
        project_id: int,
        export_type: str,
        *,
        asset_id: int | None = None,
        options_json: str | None = None,
        include_images: bool | None = None,
    ):
        if not export_type:
            raise ValueError("export_type is required")
        if options_json is None and include_images is not None:
            options_json = json_util.dumps({"include_images": bool(include_images)})
        payload = {
            "export_type": export_type,
            "asset_id": asset_id,
            "options_json": options_json,
            "status": "queued",
        }
        return self._repo.create(project_id, payload)

    def update_export(self, export_job_id: int, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        data = dict(payload)
        if "status" in data:
            data["status"] = self._normalize_status(data["status"])
        return self._repo.update(export_job_id, data)

    def mark_started(self, export_job_id: int):
        now = datetime.utcnow()
        return self._repo.update(
            export_job_id,
            {
                "status": "running",
                "started_at": now,
                "finished_at": None,
                "error_message": None,
            },
        )

    def mark_finished(
        self,
        export_job_id: int,
        *,
        asset_id: int | None = None,
        options_json: str | None = None,
    ):
        payload = {
            "status": "success",
            "finished_at": datetime.utcnow(),
        }
        if asset_id is not None:
            payload["asset_id"] = asset_id
        if options_json is not None:
            payload["options_json"] = options_json
        return self._repo.update(export_job_id, payload)

    def mark_failed(self, export_job_id: int, error_message: str):
        if not error_message:
            raise ValueError("error_message is required")
        return self._repo.update(
            export_job_id,
            {
                "status": "failed",
                "error_message": error_message,
                "finished_at": datetime.utcnow(),
            },
        )
