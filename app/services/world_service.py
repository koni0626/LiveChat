from ..repositories.world_repository import WorldRepository
from ..utils import json_util

class WorldService:
    ALLOWED_FIELDS = {
        'name',
        'era_description',
        'technology_level',
        'social_structure',
        'tone',
        'overview',
        'rules_json',
        'forbidden_json',
    }
    ALIAS_FIELDS = {
        'world_name': 'name',
        'time_period': 'era_description',
        'place_description': 'overview',
        'world_tone': 'tone',
        'forbidden_settings': 'forbidden_json',
        'important_facilities': 'rules_json',
    }

    def __init__(self, repository: WorldRepository | None = None):
        self._repo = repository or WorldRepository()

    def _ensure_project_id(self, project_id: int | str) -> int:
        try:
            project_id = int(project_id)
        except (TypeError, ValueError):
            raise ValueError('project_id must be an integer')
        if project_id < 1:
            raise ValueError('project_id must be >= 1')
        return project_id

    def _ensure_payload(self, payload: dict | None) -> dict:
        if not isinstance(payload, dict):
            raise ValueError('payload must be a dict')
        return payload

    def _normalize_text_field(self, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _normalize_json_field(self, value, field_name: str):
        if value is None or isinstance(value, str):
            return self._normalize_text_field(value)
        if isinstance(value, (dict, list)):
            return json_util.dumps(value)
        raise ValueError(f'{field_name} must be a string, dict, list, or None')

    def _normalize_world_payload(self, payload: dict, *, require_name: bool) -> dict:
        payload = self._ensure_payload(payload)
        payload = {
            self.ALIAS_FIELDS.get(key, key): value
            for key, value in payload.items()
        }
        unknown = set(payload.keys()) - self.ALLOWED_FIELDS
        if unknown:
            raise ValueError('unsupported fields: ' + ', '.join(sorted(unknown)))

        normalized = {}
        for field in self.ALLOWED_FIELDS - {'rules_json', 'forbidden_json'}:
            if field in payload:
                normalized[field] = self._normalize_text_field(payload.get(field))

        for json_field in {'rules_json', 'forbidden_json'}:
            if json_field in payload:
                normalized[json_field] = self._normalize_json_field(payload.get(json_field), json_field)

        if require_name and not normalized.get('name'):
            raise ValueError('name is required')
        if not normalized:
            raise ValueError('payload must not be empty')
        return normalized
    def get_world(self, project_id: int):
        project_id = self._ensure_project_id(project_id)
        return self._repo.get_by_project(project_id)

    def upsert_world(self, project_id: int, payload: dict):
        project_id = self._ensure_project_id(project_id)
        world = self._repo.get_by_project(project_id)
        normalized = self._normalize_world_payload(payload, require_name=world is None)
        return self._repo.upsert(project_id, normalized)
