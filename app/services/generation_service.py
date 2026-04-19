import base64
import binascii
import os
from datetime import datetime

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..models import Chapter, GenerationJob
from ..prompts.image_prompt_builder import build_image_prompt
from ..prompts.scene_prompt_builder import build_scene_prompt
from ..repositories.generation_job_repository import GenerationJobRepository
from ..repositories.scene_repository import SceneRepository
from ..utils import json_util
from .asset_service import AssetService
from .character_image_rule_service import CharacterImageRuleService
from .character_service import CharacterService
from .generated_candidate_service import GeneratedCandidateService
from .glossary_service import GlossaryService
from .project_service import ProjectService
from .scene_image_service import SceneImageService
from .scene_service import SceneService
from .scene_version_service import SceneVersionService
from .story_outline_service import StoryOutlineService
from .story_memory_service import StoryMemoryService
from .usage_log_service import UsageLogService
from .world_service import WorldService


class GenerationService:
    VALID_STATUSES = {"queued", "running", "success", "failed"}
    VALID_JOB_TYPES = {"text_generation", "image_generation", "state_extraction"}

    def __init__(
        self,
        scene_repository: SceneRepository | None = None,
        generation_job_repository: GenerationJobRepository | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        story_outline_service: StoryOutlineService | None = None,
        story_memory_service: StoryMemoryService | None = None,
        character_service: CharacterService | None = None,
        glossary_service: GlossaryService | None = None,
        scene_service: SceneService | None = None,
        scene_version_service: SceneVersionService | None = None,
        generated_candidate_service: GeneratedCandidateService | None = None,
        usage_log_service: UsageLogService | None = None,
        asset_service: AssetService | None = None,
        scene_image_service: SceneImageService | None = None,
        character_image_rule_service: CharacterImageRuleService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._scene_repo = scene_repository or SceneRepository()
        self._generation_job_repo = generation_job_repository or GenerationJobRepository()
        self._project_service = project_service or ProjectService()
        self._world_service = world_service or WorldService()
        self._story_outline_service = story_outline_service or StoryOutlineService()
        self._story_memory_service = story_memory_service or StoryMemoryService()
        self._character_service = character_service or CharacterService()
        self._glossary_service = glossary_service or GlossaryService()
        self._scene_service = scene_service or SceneService()
        self._scene_version_service = scene_version_service or SceneVersionService()
        self._generated_candidate_service = generated_candidate_service or GeneratedCandidateService()
        self._usage_log_service = usage_log_service or UsageLogService()
        self._asset_service = asset_service or AssetService()
        self._scene_image_service = scene_image_service or SceneImageService()
        self._character_image_rule_service = character_image_rule_service or CharacterImageRuleService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()

    def _normalize_status(self, status: str):
        if not status:
            raise ValueError("status is required")
        if status not in self.VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(self.VALID_STATUSES)}")
        return status

    def _normalize_job_type(self, job_type: str):
        if not job_type:
            raise ValueError("job_type is required")
        if job_type not in self.VALID_JOB_TYPES:
            raise ValueError(f"job_type must be one of {sorted(self.VALID_JOB_TYPES)}")
        return job_type

    def _get_scene(self, scene_id: int):
        return self._scene_repo.get(scene_id)

    def _get_project(self, project_id: int):
        return self._project_service.get_project(project_id)

    def _get_owner_user_id(self, project_id: int) -> int | None:
        project = self._get_project(project_id)
        if not project:
            return None
        return project.owner_user_id

    def _find_previous_scene(self, scene):
        scenes = self._scene_repo.list_by_chapter(scene.chapter_id)
        previous = None
        for item in scenes:
            if item.id == scene.id:
                break
            previous = item
        return previous

    def _resolve_scene_context(self, scene, payload: dict | None = None):
        payload = dict(payload or {})
        chapter = Chapter.query.get(scene.chapter_id)
        history_scene_limit = int(payload.get("history_scene_limit", 3))
        characters = self._character_service.list_characters(scene.project_id)
        guide_character = next((character for character in characters if character.is_guide), None)
        primary_character = guide_character or (characters[0] if characters else None)
        image_rule = None
        if primary_character:
            image_rule = self._character_image_rule_service.get_image_rule(primary_character.id)
        context = {
            "project": self._get_project(scene.project_id),
            "world": self._world_service.get_world(scene.project_id),
            "story_outline": self._story_outline_service.get_outline(scene.project_id),
            "scene": scene,
            "chapter": chapter,
            "previous_scene": self._find_previous_scene(scene),
            "recent_scenes": self._scene_service.list_previous_scenes_in_chapter(
                scene.chapter_id,
                scene.sort_order,
                scene.id,
                limit=history_scene_limit,
            ),
            "characters": characters,
            "glossary_terms": self._glossary_service.list_terms(scene.project_id),
            "story_memories": self._story_memory_service.list_recent(
                scene.project_id,
                chapter_id=scene.chapter_id,
                limit=int(payload.get("memory_limit", 8)),
            ),
            "image_rule": image_rule,
        }
        context.update(payload)
        return context

    def _resolve_reference_assets(self, scene, payload: dict | None = None):
        payload = dict(payload or {})
        use_character_base = payload.get("use_character_base", True)
        if str(use_character_base).lower() in {"0", "false", "no", "off"}:
            return []

        characters = self._character_service.list_characters(scene.project_id)
        assets = []
        seen_asset_ids = set()
        for character in characters:
            asset_id = getattr(character, "base_asset_id", None)
            if not asset_id or asset_id in seen_asset_ids:
                continue
            asset = self._asset_service.get_asset(asset_id)
            if not asset or not asset.file_path:
                continue
            seen_asset_ids.add(asset_id)
            assets.append(asset)
        return assets

    def _create_job(self, scene, *, job_type: str, payload: dict | None = None):
        payload = dict(payload or {})
        return self._generation_job_repo.create(
            {
                "project_id": scene.project_id,
                "job_type": self._normalize_job_type(job_type),
                "target_type": payload.get("target_type", "scene"),
                "target_id": payload.get("target_id", scene.id),
                "model_name": payload.get("model_name"),
                "request_json": payload.get("request_json"),
                "response_json": payload.get("response_json"),
                "status": self._normalize_status(payload.get("status", "queued")),
                "started_at": payload.get("started_at"),
                "finished_at": payload.get("finished_at"),
                "error_message": payload.get("error_message"),
            }
        )

    def _update_job(self, job: GenerationJob, **fields):
        return self._generation_job_repo.update(job, fields)

    def _mark_job_running(self, job: GenerationJob):
        return self._update_job(job, status="running", started_at=datetime.utcnow(), error_message=None)

    def _mark_job_success(self, job: GenerationJob, response_json=None):
        return self._update_job(
            job,
            status="success",
            finished_at=datetime.utcnow(),
            response_json=response_json,
            error_message=None,
        )

    def _mark_job_failed(self, job: GenerationJob, exc: Exception):
        return self._update_job(
            job,
            status="failed",
            finished_at=datetime.utcnow(),
            error_message=str(exc),
        )

    def _dump_json(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json_util.dumps(value)

    def _log_usage(self, *, project_id: int, action_type: str, usage=None, detail=None):
        user_id = self._get_owner_user_id(project_id)
        if not user_id:
            return None
        payload = {
            "user_id": user_id,
            "project_id": project_id,
            "action_type": action_type,
            "quantity": 1,
            "unit": "request",
        }
        if usage is not None or detail is not None:
            payload["detail_json"] = {"usage": usage, "detail": detail}
        try:
            return self._usage_log_service.create_log(payload)
        except Exception:
            return None

    def _create_scene_candidate(self, scene, candidate_type: str, *, content_text=None, content_json=None, tags_json=None):
        return self._generated_candidate_service.create_candidate_for_target(
            {
                "project_id": scene.project_id,
                "target_type": "scene",
                "target_id": scene.id,
                "candidate_type": candidate_type,
                "content_text": content_text,
                "content_json": content_json,
                "tags_json": tags_json,
                "is_selected": False,
            }
        )

    def _save_scene_generation_result(self, scene, result: dict, model_name: str | None):
        text = result.get("text")
        parsed = self._text_ai_client._try_parse_json(text)
        candidate = self._create_scene_candidate(
            scene,
            "scene_text",
            content_text=text,
            content_json=self._dump_json(parsed),
            tags_json=self._dump_json({"model": model_name}),
        )

        if isinstance(parsed, dict):
            update_payload = {}
            for field in ("title", "summary", "narration_text"):
                if field in parsed:
                    update_payload[field] = parsed[field]
            if "dialogues" in parsed:
                update_payload["dialogue_json"] = self._dump_json(parsed["dialogues"])
            self._scene_service.update_scene(scene.id, update_payload)
            self._scene_version_service.create_version(
                scene.id,
                {
                    "source_type": "ai",
                    "generated_by": model_name,
                    "narration_text": parsed.get("narration_text"),
                    "dialogue_json": self._dump_json(parsed.get("dialogues")),
                    "choice_json": self._dump_json(parsed.get("choices")),
                    "note_text": "generated by GenerationService.process_scene_generation",
                },
            )
        return candidate, parsed

    def _save_state_extraction_result(self, scene, result: dict, model_name: str | None):
        parsed = result.get("parsed_json")
        if parsed:
            self._scene_service.update_scene(scene.id, {"scene_state_json": self._dump_json(parsed)})
        candidate = self._create_scene_candidate(
            scene,
            "state_json",
            content_text=result.get("text"),
            content_json=self._dump_json(parsed),
            tags_json=self._dump_json({"model": model_name}),
        )
        return candidate, parsed

    def _get_storage_root(self) -> str:
        try:
            return current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        except RuntimeError:
            return os.path.join(os.getcwd(), "storage")

    def _store_generated_image(self, *, project_id: int, scene_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated image payload is invalid") from exc

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        directory = os.path.join(
            self._get_storage_root(),
            "projects",
            str(project_id),
            "generated",
            "scenes",
            str(scene_id),
        )
        os.makedirs(directory, exist_ok=True)
        file_name = f"scene_full_{timestamp}.png"
        file_path = os.path.join(directory, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)

    def _save_image_generation_result(self, scene, payload: dict, result: dict, prompt: str, reference_assets=None):
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("image generation response did not include image_base64")

        file_name, file_path, file_size = self._store_generated_image(
            project_id=scene.project_id,
            scene_id=scene.id,
            image_base64=image_base64,
        )
        asset = self._asset_service.create_asset(
            scene.project_id,
            {
                "asset_type": "generated_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": self._dump_json(
                    {
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "revised_prompt": result.get("revised_prompt"),
                        "operation": result.get("operation"),
                        "input_fidelity": result.get("input_fidelity"),
                        "reference_asset_ids": [asset.id for asset in (reference_assets or [])],
                    }
                ),
            },
        )
        scene_image = self._scene_image_service.generate_scene_images(
            scene.id,
            {
                "asset_id": asset.id,
                "image_type": payload.get("target", "scene_full"),
                "generation_job_id": payload.get("generation_job_id"),
                "prompt_text": prompt,
                "reference_asset_ids": [asset.id for asset in (reference_assets or [])],
                "state_json": scene.scene_state_json,
                "quality": payload.get("quality", "low"),
                "size": payload.get("size", "1024x1024"),
                "is_selected": 1 if payload.get("is_selected", True) else 0,
            },
        )
        if payload.get("is_selected", True):
            self._scene_image_service.select_scene_image(scene_image.id)
        self._scene_service.update_scene(
            scene.id,
            {"image_prompt_text": result.get("revised_prompt") or prompt},
        )
        return asset, scene_image

    def enqueue_scene_generation(self, scene_id: int, payload: dict | None = None):
        scene = self._get_scene(scene_id)
        if not scene:
            return None
        return self._create_job(scene, job_type="text_generation", payload=payload)

    def enqueue_state_extraction(self, scene_id: int, payload: dict | None = None):
        scene = self._get_scene(scene_id)
        if not scene:
            return None
        payload = dict(payload or {})
        payload.setdefault("target_type", "scene")
        return self._create_job(scene, job_type="state_extraction", payload=payload)

    def enqueue_image_generation(self, scene_id: int, payload: dict | None = None):
        scene = self._get_scene(scene_id)
        if not scene:
            return None
        payload = dict(payload or {})
        payload.setdefault("target_type", "scene")
        return self._create_job(scene, job_type="image_generation", payload=payload)

    def process_scene_generation(self, scene_id: int, payload: dict | None = None):
        scene = self._get_scene(scene_id)
        if not scene:
            return None
        payload = dict(payload or {})
        job = self.enqueue_scene_generation(scene_id, payload)
        self._mark_job_running(job)
        try:
            context = self._resolve_scene_context(scene, payload)
            prompt = build_scene_prompt(context, mode="scene_generation")
            result = self._text_ai_client.generate_scene(prompt, model=payload.get("model_name"))
            candidate, parsed = self._save_scene_generation_result(scene, result, result.get("model"))
            self._log_usage(
                project_id=scene.project_id,
                action_type="text_generation",
                usage=result.get("usage"),
                detail={"scene_id": scene.id, "candidate_id": candidate.id, "parsed": parsed is not None},
            )
            return self._mark_job_success(
                job,
                response_json=self._dump_json(
                    {
                        "prompt": prompt,
                        "result": {"text": result.get("text"), "usage": result.get("usage"), "model": result.get("model")},
                    }
                ),
            )
        except Exception as exc:
            self._mark_job_failed(job, exc)
            raise

    def process_state_extraction(self, scene_id: int, payload: dict | None = None):
        scene = self._get_scene(scene_id)
        if not scene:
            return None
        payload = dict(payload or {})
        job = self.enqueue_state_extraction(scene_id, payload)
        self._mark_job_running(job)
        try:
            context = self._resolve_scene_context(scene, payload)
            prompt = build_scene_prompt(context, mode="state_extraction")
            result = self._text_ai_client.extract_state_json(prompt, model=payload.get("model_name"))
            candidate, parsed = self._save_state_extraction_result(scene, result, result.get("model"))
            self._log_usage(
                project_id=scene.project_id,
                action_type="state_extraction",
                usage=result.get("usage"),
                detail={"scene_id": scene.id, "candidate_id": candidate.id, "parsed": parsed is not None},
            )
            return self._mark_job_success(
                job,
                response_json=self._dump_json(
                    {
                        "prompt": prompt,
                        "result": {"text": result.get("text"), "parsed_json": parsed, "usage": result.get("usage")},
                    }
                ),
            )
        except Exception as exc:
            self._mark_job_failed(job, exc)
            raise

    def process_image_generation(self, scene_id: int, payload: dict | None = None):
        scene = self._get_scene(scene_id)
        if not scene:
            return None
        payload = dict(payload or {})
        payload.setdefault("target_type", "scene")
        payload.setdefault("quality", "low")
        payload.setdefault("size", "1024x1024")
        payload.setdefault("use_character_base", True)
        job = self.enqueue_image_generation(scene_id, payload)
        self._mark_job_running(job)
        try:
            payload["generation_job_id"] = job.id
            context = self._resolve_scene_context(scene, payload)
            prompt = build_image_prompt(context)
            reference_assets = self._resolve_reference_assets(scene, payload)
            result = self._image_ai_client.generate_image(
                prompt,
                size=payload.get("size"),
                model=payload.get("model_name"),
                input_image_paths=[asset.file_path for asset in reference_assets],
                input_fidelity="high" if reference_assets else None,
            )
            asset, scene_image = self._save_image_generation_result(
                scene,
                payload,
                result,
                prompt,
                reference_assets=reference_assets,
            )
            self._log_usage(
                project_id=scene.project_id,
                action_type="image_generation",
                detail={
                    "scene_id": scene.id,
                    "asset_id": asset.id,
                    "scene_image_id": scene_image.id,
                    "operation": result.get("operation"),
                    "reference_asset_ids": [item.id for item in reference_assets],
                },
            )
            return self._mark_job_success(
                job,
                response_json=self._dump_json(
                    {
                        "prompt": prompt,
                        "result": {
                            "asset_id": asset.id,
                            "scene_image_id": scene_image.id,
                            "model": result.get("model"),
                            "revised_prompt": result.get("revised_prompt"),
                            "operation": result.get("operation"),
                            "input_fidelity": result.get("input_fidelity"),
                            "reference_asset_ids": [item.id for item in reference_assets],
                        },
                    }
                ),
            )
        except Exception as exc:
            self._mark_job_failed(job, exc)
            raise
