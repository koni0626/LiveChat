from ..repositories.generation_job_repository import GenerationJobRepository
from ..repositories.story_outline_repository import StoryOutlineRepository
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
    ):
        self._repo = repository or StoryOutlineRepository()
        self._generation_job_repo = generation_job_repository or GenerationJobRepository()

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
        status = self._normalize_status(payload.get('status', 'queued'))
        model_name = self._normalize_text_field(payload.get('model_name'))

        return self._generation_job_repo.create(
            {
                "project_id": project_id,
                "job_type": self.JOB_TYPE,
                "target_type": self.TARGET_TYPE,
                "status": status,
                "model_name": model_name,
                "request_json": self._serialize_request_payload(payload),
            }
        )
