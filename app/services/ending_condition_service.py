from ..api import NotFoundError
from ..repositories.ending_condition_repository import EndingConditionRepository
from ..utils import json_util


class EndingConditionService:
    ALLOWED_FIELDS = {
        "ending_type",
        "name",
        "condition_text",
        "condition_json",
        "priority",
    }

    def __init__(self, repository: EndingConditionRepository | None = None):
        self._repo = repository or EndingConditionRepository()

    def _ensure_id(self, value: int | str, field_name: str) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be an integer")
        if number < 1:
            raise ValueError(f"{field_name} must be >= 1")
        return number

    def _normalize_text(self, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _normalize_json(self, value, field_name: str):
        if value is None or isinstance(value, str):
            return self._normalize_text(value)
        if isinstance(value, (dict, list)):
            return json_util.dumps(value)
        raise ValueError(f"{field_name} must be a string, dict, list, or None")

    def _normalize_priority(self, value):
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError("priority must be an integer")

    def _normalize_payload(self, payload: dict, *, partial: bool) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        unknown = set(payload.keys()) - self.ALLOWED_FIELDS
        if unknown:
            raise ValueError("unsupported fields: " + ", ".join(sorted(unknown)))

        normalized = {}
        for field in ("ending_type", "name", "condition_text"):
            if field in payload:
                normalized[field] = self._normalize_text(payload.get(field))
        if "condition_json" in payload:
            normalized["condition_json"] = self._normalize_json(payload.get("condition_json"), "condition_json")
        if "priority" in payload:
            normalized["priority"] = self._normalize_priority(payload.get("priority"))

        if not partial:
            if not normalized.get("ending_type"):
                raise ValueError("ending_type is required")
            if not normalized.get("name"):
                raise ValueError("name is required")
        if not normalized:
            raise ValueError("payload must not be empty")
        return normalized

    def list_ending_conditions(self, project_id: int):
        project_id = self._ensure_id(project_id, "project_id")
        return self._repo.list_by_project(project_id)

    def get_ending_condition(self, ending_condition_id: int):
        ending_condition_id = self._ensure_id(ending_condition_id, "ending_condition_id")
        return self._repo.get(ending_condition_id)

    def create_ending_condition(self, project_id: int, payload: dict):
        project_id = self._ensure_id(project_id, "project_id")
        normalized = self._normalize_payload(payload, partial=False)
        return self._repo.create(project_id, normalized)

    def update_ending_condition(self, ending_condition_id: int, payload: dict):
        ending_condition_id = self._ensure_id(ending_condition_id, "ending_condition_id")
        normalized = self._normalize_payload(payload, partial=True)
        item = self._repo.update(ending_condition_id, normalized)
        if item is None:
            raise NotFoundError("not_found")
        return item

    def delete_ending_condition(self, ending_condition_id: int):
        ending_condition_id = self._ensure_id(ending_condition_id, "ending_condition_id")
        deleted = self._repo.delete(ending_condition_id)
        if not deleted:
            raise NotFoundError("not_found")
        return True
