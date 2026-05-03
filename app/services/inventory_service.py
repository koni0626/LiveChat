from __future__ import annotations

import os
from datetime import datetime

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..extensions import db
from ..models import InventoryItem
from ..utils import json_util
from . import live_chat_image_support as image_support
from .asset_service import AssetService
from .character_service import CharacterService
from .live_chat_serializer import LiveChatSerializer
from .world_service import WorldService


class InventoryService:
    def __init__(
        self,
        *,
        asset_service: AssetService | None = None,
        character_service: CharacterService | None = None,
        world_service: WorldService | None = None,
        image_ai_client: ImageAIClient | None = None,
        text_ai_client: TextAIClient | None = None,
        serializer: LiveChatSerializer | None = None,
    ):
        self._asset_service = asset_service or AssetService()
        self._character_service = character_service or CharacterService()
        self._world_service = world_service or WorldService()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._serializer = serializer or LiveChatSerializer(asset_service=self._asset_service)

    def list_items(self, *, user_id: int, project_id: int, status: str = "available"):
        query = InventoryItem.query.filter(
            InventoryItem.user_id == int(user_id),
            InventoryItem.project_id == int(project_id),
        )
        if status:
            query = query.filter(InventoryItem.status == status)
        return [self.serialize_item(row) for row in query.order_by(InventoryItem.id.desc()).all()]

    def get_available_item(self, *, item_id: int, user_id: int, project_id: int | None = None):
        query = InventoryItem.query.filter(
            InventoryItem.id == int(item_id),
            InventoryItem.user_id == int(user_id),
            InventoryItem.status == "available",
        )
        if project_id is not None:
            query = query.filter(InventoryItem.project_id == int(project_id))
        return query.first()

    def serialize_item(self, row: InventoryItem | None):
        if not row:
            return None
        asset = self._asset_service.get_asset(row.asset_id) if row.asset_id else None
        tags = []
        try:
            parsed = json_util.loads(row.tags_json) if row.tags_json else []
            tags = parsed if isinstance(parsed, list) else []
        except Exception:
            tags = []
        return {
            "id": row.id,
            "user_id": row.user_id,
            "project_id": row.project_id,
            "asset_id": row.asset_id,
            "target_character_id": row.target_character_id,
            "name": row.name,
            "description": row.description,
            "tags": tags,
            "status": row.status,
            "used_session_id": row.used_session_id,
            "used_character_id": row.used_character_id,
            "used_at": row.used_at.isoformat() if row.used_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "asset": self._serializer.serialize_asset(asset),
        }

    def _storage_root(self):
        return current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")

    def _target_character(self, project_id: int, character_id: int | None):
        characters = self._character_service.list_characters(project_id)
        if character_id:
            for character in characters:
                if int(character.id) == int(character_id):
                    return character
        return characters[0] if characters else None

    def _build_item_draft_prompt(self, project_id: int, character, payload: dict) -> str:
        world = self._world_service.get_world(project_id)
        direction = str(payload.get("prompt") or payload.get("direction") or "").strip()
        lines = [
            "Return only JSON.",
            "Create one gift inventory item for a Japanese character live chat app.",
            "The item should be something this character would plausibly like or react to.",
            "Required keys: name, description, tags, image_prompt.",
            "tags must be an array of short nouns.",
            "image_prompt must describe a single small gift item as a clean collectible item image.",
            "No readable text, no logo, no watermark.",
            "",
            f"Character: {getattr(character, 'name', '') if character else ''}",
            f"Personality: {getattr(character, 'personality', '') if character else ''}",
            f"Likes: {getattr(character, 'likes_text', '') if character else ''}",
            f"Hobbies: {getattr(character, 'hobbies_text', '') if character else ''}",
            f"Romance favorite approach: {getattr(character, 'romance_favorite_approach_text', '') if character else ''}",
            "",
            f"World name: {getattr(world, 'name', '') if world else ''}",
            f"World tone: {getattr(world, 'tone', '') if world else ''}",
            f"World technology: {getattr(world, 'technology_level', '') if world else ''}",
            f"World overview: {getattr(world, 'overview', '') if world else ''}",
        ]
        if direction:
            lines.extend(["", f"User direction: {direction}"])
        return "\n".join(lines)

    def _fallback_item_draft(self, character, payload: dict):
        name = str(payload.get("name") or payload.get("prompt") or "").strip()[:80] or "小さな贈り物"
        return {
            "name": name,
            "description": f"{getattr(character, 'name', '') or 'キャラクター'}に渡すための贈り物。",
            "tags": [name, "gift"],
            "image_prompt": f"single small gift item, {name}, clean isolated collectible item image, no text, no logo, transparent-like simple background",
        }

    def _create_item_draft(self, project_id: int, character, payload: dict):
        try:
            result = self._text_ai_client.generate_text(
                self._build_item_draft_prompt(project_id, character, payload),
                temperature=0.8,
                response_format={"type": "json_object"},
            )
            parsed = result.get("parsed_json") or self._text_ai_client._try_parse_json(result.get("text"))
            if not isinstance(parsed, dict):
                raise RuntimeError("item draft is invalid")
        except Exception:
            parsed = self._fallback_item_draft(character, payload)
        tags = [
            str(item or "").strip()[:80]
            for item in (parsed.get("tags") or [])
            if str(item or "").strip()
        ][:10]
        return {
            "name": str(parsed.get("name") or "小さな贈り物").strip()[:120],
            "description": str(parsed.get("description") or "").strip()[:500],
            "tags": tags,
            "image_prompt": str(parsed.get("image_prompt") or "").strip(),
        }

    def _build_image_prompt(self, draft: dict, character, project_id: int) -> str:
        world = self._world_service.get_world(project_id)
        parts = [
            "Create a polished square inventory item icon for a character live chat game.",
            "Show exactly one gift item, centered, clearly readable as an object, not held by a person.",
            "Use premium collectible game-item presentation, subtle shadow, clean background, no text, no logo, no watermark.",
            f"Item name: {draft.get('name') or ''}",
            f"Item description: {draft.get('description') or ''}",
            f"Item tags: {', '.join(draft.get('tags') or [])}",
            f"Target character: {getattr(character, 'name', '') if character else ''}",
            f"Character likes: {getattr(character, 'likes_text', '') if character else ''}",
            f"World tone: {getattr(world, 'tone', '') if world else ''}",
            f"World technology: {getattr(world, 'technology_level', '') if world else ''}",
        ]
        if draft.get("image_prompt"):
            parts.append(f"Visual direction: {draft['image_prompt']}")
        return "\n".join(parts)

    def generate_item(self, *, user_id: int, project_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        character_id = payload.get("character_id")
        character = self._target_character(project_id, character_id)
        draft = self._create_item_draft(project_id, character, payload)
        prompt = self._build_image_prompt(draft, character, project_id)
        result = self._image_ai_client.generate_image(
            prompt,
            size=payload.get("size") or "1024x1024",
            quality=payload.get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            provider=payload.get("provider") or payload.get("image_ai_provider"),
            output_format="png",
            background="opaque",
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("inventory image generation response did not include image_base64")
        file_name, file_path, file_size = image_support.store_generated_image(
            storage_root=self._storage_root(),
            project_id=project_id,
            session_id=0,
            image_base64=image_base64,
        )
        asset = self._asset_service.create_asset(
            project_id,
            {
                "asset_type": "inventory_item",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "inventory_item",
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "target_character_id": getattr(character, "id", None),
                    }
                ),
            },
        )
        row = InventoryItem(
            user_id=int(user_id),
            project_id=int(project_id),
            asset_id=asset.id,
            target_character_id=int(getattr(character, "id", 0) or 0) or None,
            name=draft["name"],
            description=draft["description"],
            tags_json=json_util.dumps(draft["tags"]),
            source_prompt=prompt,
            status="available",
        )
        db.session.add(row)
        db.session.commit()
        return self.serialize_item(row)

    def mark_used(self, *, item_id: int, user_id: int, session_id: int, character_id: int | None = None):
        row = self.get_available_item(item_id=item_id, user_id=user_id)
        if not row:
            return None
        row.status = "used"
        row.used_session_id = int(session_id)
        row.used_character_id = int(character_id) if character_id else None
        row.used_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return self.serialize_item(row)
