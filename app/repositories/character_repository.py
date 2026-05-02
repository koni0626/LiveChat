from datetime import datetime

from ..extensions import db
from ..models.character import Character
from ..utils import json_util


DEFAULT_MEMORY_PROFILE = {
    "likes": [],
    "dislikes": [],
    "hobbies": [],
    "taboos": [],
    "memorable_events": [],
    "romance_preferences": {
        "favorite_approach": [],
        "avoid_approach": [],
        "attraction_points": [],
        "boundaries": [],
    },
}


def _normalize_text_list(values):
    normalized = []
    seen = set()
    for item in values or []:
        text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text[:160])
    return normalized


def _text_to_list(value):
    text = str(value or "")
    return _normalize_text_list(text.replace(",", "\n").splitlines())


def _parse_memory_profile(raw_value):
    if isinstance(raw_value, dict):
        parsed = raw_value
    elif isinstance(raw_value, str) and raw_value.strip():
        try:
            parsed = json_util.loads(raw_value)
        except Exception:
            parsed = {}
    else:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    romance = parsed.get("romance_preferences") or {}
    if not isinstance(romance, dict):
        romance = {}
    return {
        "likes": _normalize_text_list(parsed.get("likes") or []),
        "dislikes": _normalize_text_list(parsed.get("dislikes") or []),
        "hobbies": _normalize_text_list(parsed.get("hobbies") or []),
        "taboos": _normalize_text_list(parsed.get("taboos") or []),
        "memorable_events": _normalize_text_list(parsed.get("memorable_events") or []),
        "romance_preferences": {
            "favorite_approach": _normalize_text_list(romance.get("favorite_approach") or []),
            "avoid_approach": _normalize_text_list(romance.get("avoid_approach") or []),
            "attraction_points": _normalize_text_list(romance.get("attraction_points") or []),
            "boundaries": _normalize_text_list(romance.get("boundaries") or []),
        },
    }


def _memory_profile_from_payload(payload: dict, current_profile=None):
    current = _parse_memory_profile(current_profile or {})
    incoming = None
    if "memory_profile" in payload:
        incoming = _parse_memory_profile(payload.get("memory_profile"))
    elif "memory_profile_json" in payload:
        incoming = _parse_memory_profile(payload.get("memory_profile_json"))
    profile = _parse_memory_profile(incoming or current)
    field_map = {
        "likes_text": ("likes", None),
        "dislikes_text": ("dislikes", None),
        "hobbies_text": ("hobbies", None),
        "taboos_text": ("taboos", None),
        "memorable_events_text": ("memorable_events", None),
        "romance_favorite_approach_text": ("romance_preferences", "favorite_approach"),
        "romance_avoid_approach_text": ("romance_preferences", "avoid_approach"),
        "romance_attraction_points_text": ("romance_preferences", "attraction_points"),
        "romance_boundaries_text": ("romance_preferences", "boundaries"),
    }
    touched = incoming is not None
    for field_name, target in field_map.items():
        if field_name not in payload:
            continue
        touched = True
        values = _text_to_list(payload.get(field_name))
        if target[1] is None:
            profile[target[0]] = values
        else:
            profile[target[0]][target[1]] = values
    if "favorite_items" in payload or "favorite_items_json" in payload:
        touched = True
        likes = _normalize_favorite_items(payload, return_list=True)
        if likes is not None:
            profile["likes"] = likes
    return json_util.dumps(profile) if touched else None


def _normalize_favorite_items(payload: dict, return_list: bool = False):
    if "favorite_items" in payload and isinstance(payload.get("favorite_items"), list):
        items = payload.get("favorite_items") or []
    elif "favorite_items_json" in payload:
        raw_value = payload.get("favorite_items_json")
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                parsed = json_util.loads(raw_value)
            except Exception:
                parsed = [line.strip() for line in raw_value.replace(",", "\n").splitlines() if line.strip()]
            items = parsed if isinstance(parsed, list) else []
        else:
            items = []
    elif "favorite_items_text" in payload:
        raw_text = str(payload.get("favorite_items_text") or "")
        items = [line.strip() for line in raw_text.replace(",", "\n").splitlines() if line.strip()]
    else:
        return None
    normalized = _normalize_text_list(items)
    if return_list:
        return normalized
    return json_util.dumps(normalized)

class CharacterRepository:
    def list_by_project(self, project_id: int, include_deleted: bool = False):
        query = Character.query.filter(Character.project_id == project_id)
        if not include_deleted:
            query = query.filter(Character.deleted_at.is_(None))
        return query.order_by(Character.id.asc()).all()

    def get(self, character_id: int, include_deleted: bool = False):
        query = Character.query.filter(Character.id == character_id)
        if not include_deleted:
            query = query.filter(Character.deleted_at.is_(None))
        return query.first()

    def create(self, project_id: int, payload: dict):
        character = Character(
            project_id=project_id,
            name=payload["name"],
            nickname=payload.get("nickname"),
            gender=payload.get("gender"),
            age_impression=payload.get("age_impression"),
            first_person=payload.get("first_person"),
            second_person=payload.get("second_person"),
            character_summary=payload.get("character_summary"),
            personality=payload.get("personality"),
            speech_style=payload.get("speech_style"),
            speech_sample=payload.get("speech_sample"),
            ng_rules=payload.get("ng_rules"),
            appearance_summary=payload.get("appearance_summary"),
            art_style=payload.get("art_style"),
            memory_notes=payload.get("memory_notes"),
            favorite_items_json=_normalize_favorite_items(payload),
            memory_profile_json=_memory_profile_from_payload(payload, DEFAULT_MEMORY_PROFILE),
            base_asset_id=payload.get("base_asset_id"),
            thumbnail_asset_id=payload.get("thumbnail_asset_id"),
        )
        db.session.add(character)
        db.session.commit()
        return character

    def update(self, character_id: int, payload: dict):
        character = self.get(character_id, include_deleted=True)
        if not character or character.deleted_at is not None:
            return None
        for field in (
            "name",
            "nickname",
            "gender",
            "age_impression",
            "first_person",
            "second_person",
            "character_summary",
            "personality",
            "speech_style",
            "speech_sample",
            "ng_rules",
            "appearance_summary",
            "art_style",
            "memory_notes",
            "base_asset_id",
            "thumbnail_asset_id",
        ):
            if field in payload:
                setattr(character, field, payload[field])
        favorite_items_json = _normalize_favorite_items(payload)
        if favorite_items_json is not None:
            character.favorite_items_json = favorite_items_json
        memory_profile_json = _memory_profile_from_payload(payload, character.memory_profile_json)
        if memory_profile_json is not None:
            character.memory_profile_json = memory_profile_json
        db.session.commit()
        return character

    def delete(self, character_id: int):
        character = self.get(character_id, include_deleted=True)
        if not character:
            return False
        if character.deleted_at is not None:
            return True
        character.deleted_at = datetime.utcnow()
        db.session.commit()
        return True

    def restore(self, character_id: int):
        character = self.get(character_id, include_deleted=True)
        if not character or character.deleted_at is None:
            return None
        character.deleted_at = None
        db.session.commit()
        return character
