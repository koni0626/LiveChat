from datetime import datetime

from ..clients.text_ai_client import TextAIClient
from ..repositories.generation_job_repository import GenerationJobRepository
from ..repositories.story_outline_repository import StoryOutlineRepository
from ..services.project_service import ProjectService
from ..services.world_service import WorldService
from ..utils import json_util

class StoryOutlineService:
    VALID_STATUSES = {'queued', 'running', 'success', 'failed'}
    JOB_TYPE = 'story_outline_generation'
    TARGET_TYPE = 'story_outline'
    ALLOWED_FIELDS = StoryOutlineRepository.MUTABLE_FIELDS

    def __init__(
        self,
        repository: StoryOutlineRepository | None = None,
        generation_job_repository: GenerationJobRepository | None = None,
        text_ai_client: TextAIClient | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
    ):
        self._repo = repository or StoryOutlineRepository()
        self._generation_job_repo = generation_job_repository or GenerationJobRepository()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._project_service = project_service or ProjectService()
        self._world_service = world_service or WorldService()

    def _ensure_payload(self, payload: dict | None) -> dict:
        if not isinstance(payload, dict):
            raise ValueError('payload must be a dict')
        return payload

    def _ensure_project_id(self, project_id: int | str) -> int:
        try:
            project_id = int(project_id)
        except (TypeError, ValueError):
            raise ValueError('project_id must be an integer')
        if project_id < 1:
            raise ValueError('project_id must be >= 1')
        return project_id

    def _normalize_text_field(self, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _normalize_outline_json(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, (dict, list)):
            return json_util.dumps(value)
        raise ValueError('outline_json must be a string, dict, list, or None')

    def _normalize_outline_payload(self, payload: dict):
        payload = self._ensure_payload(payload)
        allowed = set(self.ALLOWED_FIELDS)
        unknown = set(payload.keys()) - allowed
        if unknown:
            raise ValueError('unsupported fields: ' + ', '.join(sorted(unknown)))

        normalized = {}
        for field in self.ALLOWED_FIELDS:
            if field not in payload:
                continue
            if field == 'outline_json':
                normalized[field] = self._normalize_outline_json(payload[field])
            else:
                normalized[field] = self._normalize_text_field(payload[field])

        if not normalized:
            raise ValueError('payload must not be empty')
        return normalized

    def _serialize_request_payload(self, payload: dict) -> str | None:
        request_payload = payload.get('request')
        if isinstance(request_payload, dict):
            target = request_payload
        else:
            target = {k: v for k, v in payload.items() if k not in {'status', 'model_name'}}
        if not target:
            return None
        return json_util.dumps(target)

    def _normalize_status(self, status: str):
        if not status:
            raise ValueError('status is required')
        if status not in self.VALID_STATUSES:
            raise ValueError('status must be one of ' + ', '.join(sorted(self.VALID_STATUSES)))
        return status

    def _update_job(self, job, payload: dict):
        return self._generation_job_repo.update(job, payload)

    def _build_generation_prompt(self, project_id: int, payload: dict):
        project = self._project_service.get_project(project_id)
        world = self._world_service.get_world(project_id)
        current_outline = self.get_outline(project_id)

        context = {
            "project_title": getattr(project, "title", None),
            "project_genre": getattr(project, "genre", None),
            "project_concept": getattr(project, "concept", None),
            "world_name": getattr(world, "name", None),
            "world_overview": getattr(world, "overview", None),
            "world_tone": getattr(world, "tone", None),
            "premise": payload.get("premise") or getattr(current_outline, "premise", None),
            "protagonist_name": payload.get("protagonist_name") or getattr(current_outline, "protagonist_name", None),
            "protagonist_position": payload.get("protagonist_position") or getattr(current_outline, "protagonist_position", None),
            "main_goal": payload.get("main_goal") or getattr(current_outline, "main_goal", None),
            "branching_policy": payload.get("branching_policy") or getattr(current_outline, "branching_policy", None),
            "ending_policy": payload.get("ending_policy") or getattr(current_outline, "ending_policy", None),
            "outline_text": payload.get("outline_text") or getattr(current_outline, "outline_text", None),
        }

        lines = [
            "あなたはインタラクティブノベルの構成作家です。",
            "与えられた情報から、プレイヤーが読み進めたくなるストーリー骨子を日本語で作成してください。",
            "出力は必ず JSON オブジェクトにしてください。",
            "JSON には次のキーを含めてください: premise, protagonist_name, protagonist_position, main_goal, branching_policy, ending_policy, outline_text, chapters。",
            "chapters は 3 から 6 個の章案を配列で返し、各要素は chapter_no, title, summary, objective を含めてください。",
            "",
            "入力情報:",
        ]
        for label, key in (
            ("作品タイトル", "project_title"),
            ("ジャンル", "project_genre"),
            ("作品コンセプト", "project_concept"),
            ("世界観名", "world_name"),
            ("世界観概要", "world_overview"),
            ("世界観トーン", "world_tone"),
            ("前提", "premise"),
            ("主人公名", "protagonist_name"),
            ("主人公の立場", "protagonist_position"),
            ("主目的", "main_goal"),
            ("分岐方針", "branching_policy"),
            ("エンディング方針", "ending_policy"),
            ("既存骨子", "outline_text"),
        ):
            value = context.get(key)
            if value:
                lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    def _normalize_generated_outline(self, parsed: dict):
        normalized = {}
        for field in ("premise", "protagonist_name", "protagonist_position", "main_goal", "branching_policy", "ending_policy", "outline_text"):
            normalized[field] = self._normalize_text_field(parsed.get(field))
        chapters = parsed.get("chapters")
        normalized["outline_json"] = json_util.dumps({"chapters": chapters or []})
        return normalized

    def get_outline(self, project_id: int):
        project_id = self._ensure_project_id(project_id)
        return self._repo.get_by_project(project_id)

    def upsert_outline(self, project_id: int, payload: dict):
        project_id = self._ensure_project_id(project_id)
        normalized = self._normalize_outline_payload(payload)
        return self._repo.upsert(project_id, normalized)

    def generate_outline(self, project_id: int, payload: dict):
        project_id = self._ensure_project_id(project_id)
        payload = self._ensure_payload(payload)
        model_name = self._normalize_text_field(payload.get('model_name'))
        job = self._generation_job_repo.create(
            {
                "project_id": project_id,
                "job_type": self.JOB_TYPE,
                "target_type": self.TARGET_TYPE,
                "status": "queued",
                "model_name": model_name,
                "request_json": self._serialize_request_payload(payload),
            }
        )
        self._update_job(job, {"status": "running", "started_at": datetime.utcnow(), "error_message": None})
        try:
            prompt = self._build_generation_prompt(project_id, payload)
            result = self._text_ai_client.generate_text(
                prompt,
                model=model_name,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            parsed = self._text_ai_client._try_parse_json(result["text"])
            if not isinstance(parsed, dict):
                raise RuntimeError("story outline generation response is invalid")

            outline = self.upsert_outline(project_id, self._normalize_generated_outline(parsed))
            response_payload = {
                "prompt": prompt,
                "result": {
                    "text": result.get("text"),
                    "model": result.get("model"),
                    "usage": result.get("usage"),
                    "outline_id": outline.id,
                },
            }
            return self._update_job(
                job,
                {
                    "status": "success",
                    "model_name": result.get("model") or model_name,
                    "response_json": json_util.dumps(response_payload),
                    "finished_at": datetime.utcnow(),
                    "error_message": None,
                },
            )
        except Exception as exc:
            self._update_job(
                job,
                {
                    "status": "failed",
                    "finished_at": datetime.utcnow(),
                    "error_message": str(exc),
                },
            )
            raise
