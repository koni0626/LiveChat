from datetime import datetime

from ..utils import json_util
from .project_service import ProjectService
from ..repositories.chat_session_repository import ChatSessionRepository


class ChatSessionService:
    def __init__(
        self,
        repository: ChatSessionRepository | None = None,
        project_service: ProjectService | None = None,
    ):
        self._repo = repository or ChatSessionRepository()
        self._project_service = project_service or ProjectService()

    def list_sessions(self, project_id: int, include_deleted: bool = False):
        return self._repo.list_by_project(project_id, include_deleted=include_deleted)

    def get_session(self, session_id: int, include_deleted: bool = False):
        return self._repo.get(session_id, include_deleted=include_deleted)

    def _normalize_player_name(self, value):
        text = str(value or "").strip()
        return text or None

    def _normalize_title(self, value):
        text = str(value or "").strip()
        return text or f"Live Chat Session {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

    def _normalize_required_player_name(self, value):
        text = str(value or "").strip()
        if not text:
            raise ValueError("player_name is required")
        return text

    def _normalize_required_title(self, value):
        text = str(value or "").strip()
        if not text:
            raise ValueError("title is required")
        return text

    def _normalize_settings_json(self, value):
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, (dict, list)):
            return json_util.dumps(value)
        raise ValueError("settings_json must be a string, dict, list, or null")

    def _extract_selected_character_ids(self, settings_value):
        if settings_value is None:
            return []

        parsed = settings_value
        if isinstance(settings_value, str):
            stripped = settings_value.strip()
            if not stripped:
                return []
            parsed = json_util.loads(stripped)

        if not isinstance(parsed, dict):
            return []

        source = parsed.get("selected_character_ids")
        if not isinstance(source, list):
            single_value = parsed.get("selected_character_id")
            source = [single_value] if single_value is not None else []

        normalized = []
        for value in source:
            try:
                number = int(value)
            except (TypeError, ValueError):
                continue
            if number > 0 and number not in normalized:
                normalized.append(number)
        return normalized

    def create_session(self, project_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        project = self._project_service.get_project(project_id)
        if not project:
            return None
        selected_character_ids = self._extract_selected_character_ids(payload.get("settings_json"))
        if not selected_character_ids:
            raise ValueError("selected_character_id is required")
        return self._repo.create(
            {
                "project_id": project_id,
                "title": self._normalize_required_title(payload.get("title")),
                "session_type": payload.get("session_type") or "live_chat",
                "status": payload.get("status") or "active",
                "player_name": self._normalize_required_player_name(payload.get("player_name")),
                "settings_json": self._normalize_settings_json(payload.get("settings_json")),
            }
        )

    def update_session(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        normalized = {}
        if "title" in payload:
            normalized["title"] = self._normalize_title(payload.get("title"))
        if "status" in payload:
            normalized["status"] = str(payload.get("status") or "active").strip() or "active"
        if "player_name" in payload:
            normalized["player_name"] = self._normalize_player_name(payload.get("player_name"))
        if "active_image_id" in payload:
            normalized["active_image_id"] = payload.get("active_image_id")
        if "settings_json" in payload:
            normalized["settings_json"] = self._normalize_settings_json(payload.get("settings_json"))
        if not normalized:
            raise ValueError("payload must not be empty")
        return self._repo.update(session_id, normalized)

    def delete_session(self, session_id: int):
        return self._repo.delete(session_id)
