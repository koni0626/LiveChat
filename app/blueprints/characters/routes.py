from flask import Blueprint, request

from ...api import ForbiddenError, NotFoundError, json_response
from ..access import require_project_manage, require_project_view
from ...services.asset_service import AssetService
from ...services.character_service import CharacterService
from ...utils import json_util
import os
from flask import current_app

characters_bp = Blueprint("characters", __name__)
character_service = CharacterService()
asset_service = AssetService()
def _get_bool_query(name: str, default: bool = False) -> bool:
    value = request.args.get(name)
    if value is None:
        return default
    return str(value).lower() in {"1", "true", "yes", "on"}


def _serialize_asset_summary(asset_id: int | None):
    if not asset_id:
        return None
    asset = asset_service.get_asset(asset_id)
    if not asset:
        return None
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "file_name": asset.file_name,
        "file_path": asset.file_path,
        "media_url": _build_media_url(asset.file_path),
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
    }


def _build_media_url(file_path: str | None):
    if not file_path:
        return None
    storage_root = current_app.config.get("STORAGE_ROOT")
    normalized_path = os.path.normpath(file_path)
    normalized_root = os.path.normpath(storage_root)
    if not normalized_path.startswith(normalized_root):
        return None
    relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
    return f"/media/{relative}"


def _serialize_character(character):
    if character is None:
        return None
    try:
        favorite_items = json_util.loads(character.favorite_items_json) if character.favorite_items_json else []
    except Exception:
        favorite_items = []
    if not isinstance(favorite_items, list):
        favorite_items = []
    try:
        memory_profile = json_util.loads(character.memory_profile_json) if character.memory_profile_json else {}
    except Exception:
        memory_profile = {}
    if not isinstance(memory_profile, dict):
        memory_profile = {}
    romance = memory_profile.get("romance_preferences") or {}
    if not isinstance(romance, dict):
        romance = {}
    return {
        "id": character.id,
        "project_id": character.project_id,
        "name": character.name,
        "nickname": character.nickname,
        "gender": character.gender,
        "age_impression": character.age_impression,
        "first_person": character.first_person,
        "second_person": character.second_person,
        "personality": character.personality,
        "speech_style": character.speech_style,
        "speech_sample": character.speech_sample,
        "ng_rules": character.ng_rules,
        "appearance_summary": character.appearance_summary,
        "art_style": character.art_style,
        "memory_notes": character.memory_notes,
        "favorite_items": favorite_items,
        "favorite_items_text": "\n".join(str(item) for item in favorite_items if str(item).strip()),
        "memory_profile": memory_profile,
        "likes_text": "\n".join(memory_profile.get("likes") or favorite_items),
        "dislikes_text": "\n".join(memory_profile.get("dislikes") or []),
        "hobbies_text": "\n".join(memory_profile.get("hobbies") or []),
        "taboos_text": "\n".join(memory_profile.get("taboos") or []),
        "memorable_events_text": "\n".join(memory_profile.get("memorable_events") or []),
        "romance_favorite_approach_text": "\n".join(romance.get("favorite_approach") or []),
        "romance_avoid_approach_text": "\n".join(romance.get("avoid_approach") or []),
        "romance_attraction_points_text": "\n".join(romance.get("attraction_points") or []),
        "romance_boundaries_text": "\n".join(romance.get("boundaries") or []),
        "base_asset_id": character.base_asset_id,
        "base_asset": _serialize_asset_summary(character.base_asset_id),
        "thumbnail_asset_id": character.thumbnail_asset_id,
        "thumbnail_asset": _serialize_asset_summary(character.thumbnail_asset_id),
        "created_at": character.created_at.isoformat() if getattr(character, "created_at", None) else None,
        "updated_at": character.updated_at.isoformat() if getattr(character, "updated_at", None) else None,
        "deleted_at": character.deleted_at.isoformat() if getattr(character, "deleted_at", None) else None,
    }


@characters_bp.route("/projects/<int:project_id>/characters", methods=["GET"])
def list_characters(project_id: int):
    require_project_view(project_id)
    include_deleted = _get_bool_query("include_deleted", default=False)
    search = request.args.get("q") or request.args.get("search")
    characters = character_service.list_characters(project_id, include_deleted=include_deleted)
    if search:
        keyword = search.strip().lower()
        characters = [
            character
            for character in characters
            if keyword in (character.name or "").lower()
            or keyword in (character.nickname or "").lower()
            or keyword in (character.gender or "").lower()
            or keyword in (character.speech_style or "").lower()
            or keyword in (character.appearance_summary or "").lower()
        ]
    data = [_serialize_character(character) for character in characters]
    meta = {"project_id": project_id, "count": len(data)}
    if search:
        meta["search"] = search
    return json_response(data, meta=meta)


@characters_bp.route("/projects/<int:project_id>/characters", methods=["POST"])
def create_character(project_id: int):
    require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    try:
        character = character_service.create_character(project_id, payload)
    except (KeyError, ValueError) as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_character(character), status=201)


@characters_bp.route("/projects/<int:project_id>/characters/draft", methods=["POST"])
def generate_character_draft(project_id: int):
    require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    try:
        draft = character_service.generate_character_draft(project_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    return json_response({"project_id": project_id, "draft": draft})


@characters_bp.route("/characters/<int:character_id>", methods=["GET"])
def get_character(character_id: int):
    include_deleted = _get_bool_query("include_deleted", default=False)
    character = character_service.get_character(character_id, include_deleted=include_deleted)
    if not character:
        raise NotFoundError()
    require_project_view(character.project_id)
    return json_response(_serialize_character(character))


@characters_bp.route("/characters/<int:character_id>", methods=["PATCH"])
def update_character(character_id: int):
    payload = request.get_json(silent=True) or {}
    existing = character_service.get_character(character_id)
    if not existing:
        raise NotFoundError()
    require_project_manage(existing.project_id)
    try:
        character = character_service.update_character(character_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not character:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_character(character))


@characters_bp.route("/characters/<int:character_id>/base-image/generate", methods=["POST"])
def generate_character_base_image(character_id: int):
    payload = request.get_json(silent=True) or {}
    existing = character_service.get_character(character_id)
    if not existing:
        raise NotFoundError()
    require_project_manage(existing.project_id)
    try:
        character = character_service.generate_base_image(character_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    if not character:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_character(character))


@characters_bp.route("/characters/<int:character_id>", methods=["DELETE"])
def delete_character(character_id: int):
    existing = character_service.get_character(character_id)
    if not existing:
        raise NotFoundError()
    require_project_manage(existing.project_id)
    deleted = character_service.delete_character(character_id)
    if not deleted:
        return json_response({"message": "not_found"}, status=404)
    return json_response({"character_id": character_id, "deleted": True})
