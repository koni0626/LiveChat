import json

from ..repositories.scene_choice_repository import SceneChoiceRepository


class SceneChoiceService:
    ALLOWED_FIELDS = {
        "choice_text",
        "next_scene_id",
        "condition_json",
        "result_summary",
        "sort_order",
    }
    def __init__(self, repository: SceneChoiceRepository | None = None):
        self._repo = repository or SceneChoiceRepository()

    def list_choices(self, scene_id: int):
        scene_id = self._ensure_int(scene_id, "scene_id", minimum=1)
        return self._repo.list_by_scene(scene_id)

    def get_choice(self, choice_id: int):
        choice_id = self._ensure_int(choice_id, "choice_id", minimum=1)
        return self._repo.get(choice_id)

    def create_choice(self, scene_id: int, payload: dict):
        scene_id = self._ensure_int(scene_id, "scene_id", minimum=1)
        normalized = self._normalize_choice_payload(payload, partial=False)
        return self._repo.create(scene_id, normalized)

    def update_choice(self, choice_id: int, payload: dict):
        choice_id = self._ensure_int(choice_id, "choice_id", minimum=1)
        normalized = self._normalize_choice_payload(payload, partial=True)
        return self._repo.update(choice_id, normalized)

    def delete_choice(self, choice_id: int):
        choice_id = self._ensure_int(choice_id, "choice_id", minimum=1)
        return self._repo.delete(choice_id)

    def _ensure_int(self, value, field_name: str, *, allow_none: bool = False, minimum: int | None = None):
        if value is None:
            if allow_none:
                return None
            raise ValueError(f"{field_name} is required")
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be an integer")
        if minimum is not None and value < minimum:
            raise ValueError(f"{field_name} must be >= {minimum}")
        return value

    def _normalize_choice_payload(self, payload: dict, *, partial: bool) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")

        normalized: dict[str, object] = {}

        if not partial and "choice_text" not in payload:
            raise ValueError("choice_text is required")

        if "choice_text" in payload:
            choice_text = str(payload.get("choice_text", "")).strip()
            if not choice_text:
                raise ValueError("choice_text is required")
            normalized["choice_text"] = choice_text

        if "next_scene_id" in payload:
            normalized["next_scene_id"] = self._ensure_int(
                payload.get("next_scene_id"),
                "next_scene_id",
                allow_none=True,
                minimum=1,
            )

        if "sort_order" in payload:
            normalized["sort_order"] = self._ensure_int(
                payload.get("sort_order"),
                "sort_order",
                minimum=1,
            )

        if "condition_json" in payload:
            condition_value = payload.get("condition_json")
            if condition_value is None or isinstance(condition_value, str):
                normalized["condition_json"] = condition_value
            elif isinstance(condition_value, (dict, list)):
                normalized["condition_json"] = json.dumps(condition_value, ensure_ascii=False)
            else:
                raise ValueError("condition_json must be a string, dict, list, or None")

        if "result_summary" in payload:
            result_summary = payload.get("result_summary")
            normalized["result_summary"] = None if result_summary is None else str(result_summary).strip()

        unexpected_keys = set(payload.keys()) - self.ALLOWED_FIELDS
        if unexpected_keys:
            raise ValueError(f"unsupported fields: {sorted(unexpected_keys)}")

        if partial and not normalized:
            raise ValueError("payload must not be empty")

        return normalized
