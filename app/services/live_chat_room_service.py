from __future__ import annotations

import os

from flask import current_app

from ..repositories.chat_session_repository import ChatSessionRepository
from ..repositories.live_chat_room_repository import LiveChatRoomRepository
from .asset_service import AssetService
from .character_service import CharacterService
from .closet_service import ClosetService
from .project_service import ProjectService


class LiveChatRoomService:
    VALID_STATUSES = {"draft", "published", "archived"}

    def __init__(
        self,
        repository: LiveChatRoomRepository | None = None,
        project_service: ProjectService | None = None,
        character_service: CharacterService | None = None,
        chat_session_repository: ChatSessionRepository | None = None,
        asset_service: AssetService | None = None,
        closet_service: ClosetService | None = None,
    ):
        self._repo = repository or LiveChatRoomRepository()
        self._project_service = project_service or ProjectService()
        self._character_service = character_service or CharacterService()
        self._chat_session_repo = chat_session_repository or ChatSessionRepository()
        self._asset_service = asset_service or AssetService()
        self._closet_service = closet_service or ClosetService()

    def list_rooms(self, project_id: int, *, include_unpublished: bool = False):
        status = None if include_unpublished else "published"
        return self._repo.list_by_project(project_id, status=status)

    def get_room(self, room_id: int):
        return self._repo.get(room_id)

    def get_room_by_character(self, character_id: int):
        return self._repo.get_by_character(character_id)

    def serialize_room(self, room, *, include_counts: bool = False, owner_user_id: int | None = None):
        if not room:
            return None
        character = self._character_service.get_character(room.character_id)
        thumbnail_asset = self._serialize_asset_summary(getattr(character, "thumbnail_asset_id", None) if character else None)
        base_asset = self._serialize_asset_summary(getattr(character, "base_asset_id", None) if character else None)
        default_outfit = self._closet_service.serialize_outfit(
            self._closet_service.resolve_outfit(room.character_id, getattr(room, "default_outfit_id", None))
        ) if getattr(room, "default_outfit_id", None) else None
        payload = {
            "id": room.id,
            "project_id": room.project_id,
            "created_by_user_id": room.created_by_user_id,
            "character_id": room.character_id,
            "default_outfit_id": getattr(room, "default_outfit_id", None),
            "default_outfit": default_outfit,
            "title": room.title,
            "description": room.description,
            "conversation_objective": room.conversation_objective,
            "proxy_player_objective": getattr(room, "proxy_player_objective", None),
            "proxy_player_gender": getattr(room, "proxy_player_gender", None),
            "proxy_player_speech_style": getattr(room, "proxy_player_speech_style", None),
            "status": room.status,
            "sort_order": room.sort_order,
            "created_at": room.created_at.isoformat() if getattr(room, "created_at", None) else None,
            "updated_at": room.updated_at.isoformat() if getattr(room, "updated_at", None) else None,
            "character": (
                {
                    "id": character.id,
                    "name": character.name,
                    "nickname": getattr(character, "nickname", None),
                    "thumbnail_asset_id": getattr(character, "thumbnail_asset_id", None),
                    "base_asset_id": getattr(character, "base_asset_id", None),
                    "thumbnail_asset": thumbnail_asset,
                    "base_asset": base_asset,
                }
                if character
                else None
            ),
        }
        if include_counts:
            sessions = self._chat_session_repo.list_by_room(room.id)
            payload["session_count"] = len(sessions)
            if owner_user_id is not None:
                payload["my_session_count"] = len([item for item in sessions if item.owner_user_id == owner_user_id])
        return payload

    def _build_media_url(self, file_path: str | None):
        if not file_path:
            return None
        try:
            storage_root = current_app.config.get("STORAGE_ROOT")
        except RuntimeError:
            storage_root = None
        if not storage_root:
            return None
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        if not normalized_path.startswith(normalized_root):
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"

    def _serialize_asset_summary(self, asset_id: int | None):
        if not asset_id:
            return None
        asset = self._asset_service.get_asset(asset_id)
        if not asset:
            return None
        return {
            "id": asset.id,
            "file_name": asset.file_name,
            "mime_type": asset.mime_type,
            "media_url": self._build_media_url(asset.file_path),
        }

    def serialize_rooms(self, rooms, *, include_counts: bool = False, owner_user_id: int | None = None):
        return [
            self.serialize_room(room, include_counts=include_counts, owner_user_id=owner_user_id)
            for room in rooms
        ]

    def create_room(self, project_id: int, payload: dict | None, created_by_user_id: int):
        payload = dict(payload or {})
        project = self._project_service.get_project(project_id)
        if not project:
            return None
        normalized = self._normalize_payload(project_id, payload, created_by_user_id=created_by_user_id, require_all=True)
        return self._repo.create(normalized)

    def build_objective_draft(self, project_id: int, payload: dict | None):
        payload = dict(payload or {})
        try:
            character_id = int(payload.get("character_id") or 0)
        except (TypeError, ValueError):
            character_id = 0
        if character_id <= 0:
            raise ValueError("character_id is required")
        character = self._character_service.get_character(character_id)
        if not character or character.project_id != project_id:
            raise ValueError("character_id is invalid")
        return self._character_service.build_default_live_chat_room_payload(character)

    def update_room(self, room_id: int, payload: dict | None):
        payload = dict(payload or {})
        room = self.get_room(room_id)
        if not room:
            return None
        normalized = self._normalize_payload(
            room.project_id,
            payload,
            created_by_user_id=room.created_by_user_id,
            require_all=False,
            current_character_id=room.character_id,
        )
        if not normalized:
            raise ValueError("payload must not be empty")
        return self._repo.update(room_id, normalized)

    def delete_room(self, room_id: int):
        return self._repo.delete(room_id)

    def build_room_snapshot(self, room):
        character = self._character_service.get_character(room.character_id)
        default_outfit = self._closet_service.serialize_outfit(
            self._closet_service.resolve_outfit(room.character_id, getattr(room, "default_outfit_id", None))
        ) if getattr(room, "default_outfit_id", None) else None
        return {
            "room_id": room.id,
            "room_title": room.title,
            "conversation_objective": room.conversation_objective,
            "proxy_player_objective": getattr(room, "proxy_player_objective", None),
            "proxy_player_gender": getattr(room, "proxy_player_gender", None),
            "proxy_player_speech_style": getattr(room, "proxy_player_speech_style", None),
            "character_id": room.character_id,
            "character_name": character.name if character else None,
            "default_outfit_id": getattr(room, "default_outfit_id", None),
            "default_outfit_name": default_outfit.get("name") if isinstance(default_outfit, dict) else None,
            "status": room.status,
            "version_updated_at": room.updated_at.isoformat() if getattr(room, "updated_at", None) else None,
        }

    def _normalize_payload(
        self,
        project_id: int,
        payload: dict,
        *,
        created_by_user_id: int,
        require_all: bool,
        current_character_id: int | None = None,
    ):
        normalized = {}
        if require_all or "title" in payload:
            title = str(payload.get("title") or "").strip()
            if not title:
                raise ValueError("title is required")
            normalized["title"] = title
        if require_all or "conversation_objective" in payload:
            objective = str(payload.get("conversation_objective") or "").strip()
            if not objective:
                raise ValueError("conversation_objective is required")
            normalized["conversation_objective"] = objective
        if "proxy_player_objective" in payload or require_all:
            normalized["proxy_player_objective"] = str(payload.get("proxy_player_objective") or "").strip() or None
        if "proxy_player_gender" in payload or require_all:
            normalized["proxy_player_gender"] = str(payload.get("proxy_player_gender") or "").strip() or None
        if "proxy_player_speech_style" in payload or require_all:
            normalized["proxy_player_speech_style"] = str(payload.get("proxy_player_speech_style") or "").strip() or None
        if "description" in payload:
            normalized["description"] = str(payload.get("description") or "").strip() or None
        if require_all or "character_id" in payload:
            try:
                character_id = int(payload.get("character_id") or 0)
            except (TypeError, ValueError):
                character_id = 0
            if character_id <= 0:
                raise ValueError("character_id is required")
            character = self._character_service.get_character(character_id)
            if not character or character.project_id != project_id:
                raise ValueError("character_id is invalid")
            normalized["character_id"] = character_id
        effective_character_id = normalized.get("character_id") or current_character_id
        if "default_outfit_id" in payload or require_all or "character_id" in normalized:
            raw_outfit_id = payload.get("default_outfit_id")
            try:
                outfit_id = int(raw_outfit_id or 0)
            except (TypeError, ValueError):
                outfit_id = 0
            if outfit_id:
                character_id_for_outfit = normalized.get("character_id") or effective_character_id
                outfit = self._closet_service.resolve_outfit(int(character_id_for_outfit or 0), outfit_id)
                if not outfit or outfit.id != outfit_id or outfit.project_id != project_id:
                    raise ValueError("default_outfit_id is invalid")
                normalized["default_outfit_id"] = outfit_id
            else:
                normalized["default_outfit_id"] = None
        if "status" in payload or require_all:
            status = str(payload.get("status") or "draft").strip() or "draft"
            if status not in self.VALID_STATUSES:
                raise ValueError("status is invalid")
            normalized["status"] = status
        if "sort_order" in payload:
            try:
                normalized["sort_order"] = int(payload.get("sort_order") or 0)
            except (TypeError, ValueError):
                normalized["sort_order"] = 0
        if require_all:
            normalized["project_id"] = project_id
            normalized["created_by_user_id"] = created_by_user_id
        return normalized
