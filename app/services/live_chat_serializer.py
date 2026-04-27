from __future__ import annotations

import os

from flask import current_app

from ..utils import json_util
from ..repositories.feed_repository import FeedRepository
from .asset_service import AssetService


class LiveChatSerializer:
    """DTO serialization helpers shared by live chat services."""

    def __init__(self, *, asset_service: AssetService):
        self._asset_service = asset_service
        self._feed_repository = FeedRepository()

    def load_json(self, value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return json_util.loads(stripped)
        except Exception:
            return value

    def build_media_url(self, file_path: str | None):
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

    def serialize_asset(self, asset):
        if asset is None:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "file_path": asset.file_path,
            "mime_type": asset.mime_type,
            "file_size": asset.file_size,
            "width": asset.width,
            "height": asset.height,
            "media_url": self.build_media_url(asset.file_path),
        }

    def serialize_character(self, character):
        base_asset = self._asset_service.get_asset(character.base_asset_id) if getattr(character, "base_asset_id", None) else None
        memory_profile = self.load_json(getattr(character, "memory_profile_json", None)) or {}
        if not isinstance(memory_profile, dict):
            memory_profile = {}
        feed_profile = self._feed_repository.get_profile(character.id)
        return {
            "id": character.id,
            "name": character.name,
            "nickname": character.nickname,
            "gender": character.gender,
            "first_person": character.first_person,
            "second_person": character.second_person,
            "personality": character.personality,
            "speech_style": character.speech_style,
            "speech_sample": character.speech_sample,
            "ng_rules": character.ng_rules,
            "appearance_summary": character.appearance_summary,
            "art_style": getattr(character, "art_style", None),
            "memory_notes": getattr(character, "memory_notes", None),
            "favorite_items": self.load_json(getattr(character, "favorite_items_json", None)) or [],
            "memory_profile": memory_profile,
            "feed_profile_text": getattr(feed_profile, "profile_text", None) if feed_profile else None,
            "base_asset": self.serialize_asset(base_asset),
        }

    def serialize_session(self, row):
        return {
            "id": row.id,
            "project_id": row.project_id,
            "room_id": getattr(row, "room_id", None),
            "owner_user_id": getattr(row, "owner_user_id", None),
            "title": row.title,
            "session_type": row.session_type,
            "status": row.status,
            "privacy_status": getattr(row, "privacy_status", "private"),
            "active_image_id": row.active_image_id,
            "player_name": row.player_name,
            "settings_json": self.load_json(row.settings_json),
            "room_snapshot_json": self.load_json(getattr(row, "room_snapshot_json", None)),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def serialize_message(self, row):
        return {
            "id": row.id,
            "session_id": row.session_id,
            "sender_type": row.sender_type,
            "speaker_name": row.speaker_name,
            "message_text": row.message_text,
            "order_no": row.order_no,
            "message_role": row.message_role,
            "state_snapshot_json": self.load_json(row.state_snapshot_json),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
        }

    def serialize_state(self, row):
        if row is None:
            return {
                "state_json": {},
                "narration_note": None,
                "visual_prompt_text": None,
            }
        return {
            "id": row.id,
            "session_id": row.session_id,
            "state_json": self.load_json(row.state_json) or {},
            "narration_note": row.narration_note,
            "visual_prompt_text": row.visual_prompt_text,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }
