from __future__ import annotations

import os

from flask import current_app

from ..repositories.chat_session_repository import ChatSessionRepository
from ..repositories.live_chat_room_repository import LiveChatRoomRepository
from .asset_service import AssetService
from .character_service import CharacterService
from .closet_service import ClosetService
from .project_service import ProjectService
from ..clients.text_ai_client import TextAIClient


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
        text_ai_client: TextAIClient | None = None,
    ):
        self._repo = repository or LiveChatRoomRepository()
        self._project_service = project_service or ProjectService()
        self._character_service = character_service or CharacterService()
        self._chat_session_repo = chat_session_repository or ChatSessionRepository()
        self._asset_service = asset_service or AssetService()
        self._closet_service = closet_service or ClosetService()
        self._text_ai_client = text_ai_client or TextAIClient()

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
        bromide_asset = self._serialize_asset_summary(getattr(character, "bromide_asset_id", None) if character else None)
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
                    "introduction_text": getattr(character, "introduction_text", None),
                    "thumbnail_asset_id": getattr(character, "thumbnail_asset_id", None),
                    "bromide_asset_id": getattr(character, "bromide_asset_id", None),
                    "base_asset_id": getattr(character, "base_asset_id", None),
                    "thumbnail_asset": thumbnail_asset,
                    "bromide_asset": bromide_asset,
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

    def build_description_draft(self, project_id: int, payload: dict | None):
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
        prompt = self._build_description_draft_prompt(character, payload)
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.75,
            max_tokens=500,
        )
        text = self._normalize_description_text(result.get("text"))
        if not text:
            raise RuntimeError("description draft response is empty")
        return {"description": text}

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

    def _build_description_draft_prompt(self, character, payload: dict) -> str:
        title = str(payload.get("title") or "").strip()
        objective = str(payload.get("conversation_objective") or "").strip()
        current_description = str(payload.get("description") or "").strip()
        lines = [
            "日本語で、ライブチャットのルーム紹介文を作成してください。",
            "ユーザーがルーム一覧で読み、どんな会話ができるか直感的に分かる短い紹介です。",
            "キャラクター本人の魅力、距離感、会話したくなる入口を入れてください。",
            "長さは120〜220字程度。Markdown、箇条書き、見出し、引用符、前置きは禁止。本文だけを返してください。",
            "",
            f"キャラクター名: {character.name}",
        ]
        for label, value in (
            ("ルーム名", title),
            ("既存の紹介文", current_description),
            ("キャラクター自己紹介", getattr(character, "introduction_text", None)),
            ("概要", getattr(character, "character_summary", None)),
            ("性格", getattr(character, "personality", None)),
            ("話し方", getattr(character, "speech_style", None)),
            ("セリフ例", getattr(character, "speech_sample", None)),
            ("見た目", getattr(character, "appearance_summary", None)),
            ("ルーム内の会話方針", objective),
        ):
            text = self._shorten_for_prompt(value, limit=700)
            if text:
                lines.append(f"{label}: {text}")
        return "\n".join(lines)

    def _normalize_description_text(self, value) -> str:
        text = str(value or "").strip().replace("\r\n", "\n")
        if text.startswith("```"):
            text = text.strip("`").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = " ".join(lines).strip()
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("「") and text.endswith("」")):
            text = text[1:-1].strip()
        return text[:600]

    def _shorten_for_prompt(self, value, limit: int = 500) -> str:
        text = str(value or "").strip().replace("\r\n", "\n")
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

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
