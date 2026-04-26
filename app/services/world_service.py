from ..repositories.world_repository import WorldRepository
from ..utils import json_util
from ..clients.text_ai_client import TextAIClient
from .project_service import ProjectService

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

    def __init__(
        self,
        repository: WorldRepository | None = None,
        text_ai_client: TextAIClient | None = None,
        project_service: ProjectService | None = None,
    ):
        self._repo = repository or WorldRepository()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._project_service = project_service or ProjectService()

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

    def generate_world_draft(self, project_id: int, payload: dict | None = None) -> dict:
        project_id = self._ensure_project_id(project_id)
        payload = payload if isinstance(payload, dict) else {}
        project = self._project_service.get_project(project_id)
        current_world = self.get_world(project_id)
        prompt = self._build_world_draft_prompt(project, current_world, payload)
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.75,
            response_format={"type": "json_object"},
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("world draft response is invalid")
        return self._normalize_world_draft(parsed)

    def has_usable_world(self, project_id: int) -> bool:
        world = self.get_world(project_id)
        if not world:
            return False
        values = [
            world.name,
            world.era_description,
            world.technology_level,
            world.social_structure,
            world.tone,
            world.overview,
            world.rules_json,
            world.forbidden_json,
        ]
        return any(str(value or "").strip() for value in values)

    def _build_world_draft_prompt(self, project, current_world, payload: dict) -> str:
        ui_fields = payload.get("ui_fields") if isinstance(payload.get("ui_fields"), dict) else payload
        lines = [
            "Return only JSON.",
            "Create a strong draft world setting for a Japanese character live chat tool.",
            "The user will edit it later, so make it concrete, reusable, and suitable for AI character conversation.",
            "Required JSON keys: world_name, world_tone, time_period, place_description, technology_level, social_structure, important_facilities, forbidden_settings.",
            "All values must be Japanese strings written in Markdown-friendly style. important_facilities and forbidden_settings may contain headings and bullet lists.",
            "Avoid generic fantasy filler. Make the setting specific enough to guide character behavior and image generation.",
        ]
        if project:
            lines.extend(
                [
                    "",
                    "Project:",
                    f"title: {project.title}",
                    f"description: {project.summary or ''}",
                    f"status: {project.status}",
                ]
            )
        if current_world:
            lines.extend(
                [
                    "",
                    "Existing world setting to improve or complete:",
                    f"name: {current_world.name or ''}",
                    f"tone: {current_world.tone or ''}",
                    f"era: {current_world.era_description or ''}",
                    f"place: {current_world.overview or ''}",
                    f"technology: {current_world.technology_level or ''}",
                    f"social_structure: {current_world.social_structure or ''}",
                    f"rules: {current_world.rules_json or ''}",
                    f"forbidden: {current_world.forbidden_json or ''}",
                ]
            )
        if ui_fields:
            lines.append("")
            lines.append("Current form input:")
            for key, value in ui_fields.items():
                lines.append(f"{key}: {value or ''}")
        return "\n".join(lines)

    def _normalize_world_draft(self, parsed: dict) -> dict:
        fields = {
            "world_name": "未設定の世界",
            "world_tone": "",
            "time_period": "",
            "place_description": "",
            "technology_level": "",
            "social_structure": "",
            "important_facilities": "",
            "forbidden_settings": "",
        }
        return {key: str(parsed.get(key) or default).strip() for key, default in fields.items()}
