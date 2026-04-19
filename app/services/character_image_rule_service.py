from ..models import Character
from ..repositories.character_image_rule_repository import CharacterImageRuleRepository


class CharacterImageRuleService:
    ALLOWED_FIELDS = {
        "hair_rule",
        "face_rule",
        "ear_rule",
        "accessory_rule",
        "outfit_rule",
        "style_rule",
        "negative_rule",
        "default_quality",
        "default_size",
        "prompt_prefix",
        "prompt_suffix",
    }
    VALID_QUALITIES = {"low", "medium", "high"}
    VALID_SIZES = {"1024x1024", "1024x1536", "1536x1024"}

    def __init__(self, repository: CharacterImageRuleRepository | None = None):
        self._repo = repository or CharacterImageRuleRepository()

    def _ensure_character_id(self, character_id: int | str) -> int:
        try:
            character_id = int(character_id)
        except (TypeError, ValueError):
            raise ValueError("character_id must be an integer")
        if character_id < 1:
            raise ValueError("character_id must be >= 1")
        return character_id

    def _ensure_character_exists(self, character_id: int):
        character = Character.query.filter(Character.id == character_id, Character.deleted_at.is_(None)).first()
        if not character:
            return None
        return character

    def _normalize_text(self, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _normalize_payload(self, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        unknown = set(payload.keys()) - self.ALLOWED_FIELDS
        if unknown:
            raise ValueError("unsupported fields: " + ", ".join(sorted(unknown)))
        if not payload:
            raise ValueError("payload must not be empty")

        normalized = {}
        for field in self.ALLOWED_FIELDS:
            if field not in payload:
                continue
            if field == "default_quality":
                value = self._normalize_text(payload[field])
                if value is None:
                    value = "low"
                if value not in self.VALID_QUALITIES:
                    raise ValueError("default_quality must be one of low, medium, high")
                normalized[field] = value
            elif field == "default_size":
                value = self._normalize_text(payload[field])
                if value is None:
                    value = "1024x1024"
                if value not in self.VALID_SIZES:
                    raise ValueError("default_size must be one of 1024x1024, 1024x1536, 1536x1024")
                normalized[field] = value
            else:
                normalized[field] = self._normalize_text(payload[field])
        return normalized

    def get_image_rule(self, character_id: int):
        character_id = self._ensure_character_id(character_id)
        character = self._ensure_character_exists(character_id)
        if not character:
            return None
        return self._repo.get_by_character_id(character_id)

    def upsert_image_rule(self, character_id: int, payload: dict):
        character_id = self._ensure_character_id(character_id)
        character = self._ensure_character_exists(character_id)
        if not character:
            return None
        normalized = self._normalize_payload(payload)
        return self._repo.upsert(character_id, normalized)
