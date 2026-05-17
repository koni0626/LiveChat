from __future__ import annotations

import base64
import binascii
import hashlib
import os
import uuid
from datetime import datetime

from flask import current_app
from PIL import Image

from ..clients.image_ai_client import ImageAIClient
from ..repositories.asset_repository import AssetRepository
from ..repositories.character_repository import CharacterRepository
from ..utils import json_util
from .asset_service import AssetService


class StampService:
    ASSET_TYPE = "character_stamp"

    def __init__(
        self,
        *,
        asset_service: AssetService | None = None,
        asset_repository: AssetRepository | None = None,
        character_repository: CharacterRepository | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._asset_service = asset_service or AssetService()
        self._assets = asset_repository or AssetRepository()
        self._characters = character_repository or CharacterRepository()
        self._image_ai_client = image_ai_client or ImageAIClient()

    def list_stamps(self, project_id: int, *, character_id: int | None = None):
        stamps = self._asset_service.list_assets(project_id, asset_type=self.ASSET_TYPE)
        if character_id:
            stamps = [
                stamp
                for stamp in stamps
                if int((self._metadata(stamp) or {}).get("character_id") or 0) == int(character_id)
            ]
        return [self._serialize_stamp(stamp) for stamp in reversed(stamps)]

    def get_stamp(self, project_id: int, asset_id: int):
        stamp = self._asset_service.get_asset(asset_id)
        if not stamp or int(stamp.project_id or 0) != int(project_id) or stamp.asset_type != self.ASSET_TYPE:
            return None
        return self._serialize_stamp(stamp)

    def delete_stamp(self, project_id: int, asset_id: int) -> bool:
        stamp = self._asset_service.get_asset(asset_id)
        if not stamp or int(stamp.project_id or 0) != int(project_id) or stamp.asset_type != self.ASSET_TYPE:
            return False
        return self._asset_service.delete_asset(asset_id)

    def generate_stamp(self, project_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        character_id = self._int_value(payload.get("character_id"))
        if not character_id:
            raise ValueError("character_id is required")
        text = str(payload.get("text") or "").strip()
        if not text:
            raise ValueError("text is required")
        if len(text) > 32:
            raise ValueError("text must be 32 characters or fewer")
        character = self._characters.get(character_id)
        if not character or int(character.project_id) != int(project_id):
            raise ValueError("character_id is invalid")
        base_asset = self._assets.get(character.base_asset_id) if character.base_asset_id else None
        if not base_asset or not getattr(base_asset, "file_path", None):
            raise ValueError("character base image is required")

        quality = self._normalize_quality(payload.get("quality"))
        size = self._normalize_size(payload.get("size"))
        prompt = self._build_stamp_prompt(character, text, payload)
        result = self._image_ai_client.generate_image(
            prompt,
            size=size,
            quality=quality,
            model=payload.get("model") or payload.get("image_ai_model"),
            provider=payload.get("provider") or payload.get("image_ai_provider"),
            output_format="png",
            background="opaque",
            input_image_paths=[base_asset.file_path],
            input_fidelity="high",
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("stamp image generation response did not include image_base64")
        image_bytes = self._decode_image_base64(image_base64)
        width, height = self._image_dimensions(image_bytes, fallback=self._parse_size(size))
        file_name, file_path = self._store_stamp_image(project_id, character.id, text, image_bytes)
        asset = self._asset_service.create_asset(
            project_id,
            {
                "asset_type": self.ASSET_TYPE,
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": len(image_bytes),
                "width": width,
                "height": height,
                "checksum": hashlib.sha256(image_bytes).hexdigest(),
                "metadata_json": json_util.dumps(
                    {
                        "source": "stamp_generator",
                        "character_id": character.id,
                        "character_name": character.name,
                        "text": text,
                        "style": payload.get("style") or "cute_sticker",
                        "base_asset_id": base_asset.id,
                        "prompt": prompt,
                        "quality": quality,
                        "size": size,
                        "model": payload.get("model") or payload.get("image_ai_model"),
                        "provider": payload.get("provider") or payload.get("image_ai_provider"),
                        "revised_prompt": result.get("revised_prompt"),
                        "generated_at": datetime.utcnow().isoformat(),
                    }
                ),
            },
        )
        return self._serialize_stamp(asset)

    def _build_stamp_prompt(self, character, text: str, payload: dict) -> str:
        style_note = str(payload.get("style_instruction") or "").strip()
        appearance = str(getattr(character, "appearance_summary", "") or "").strip()
        personality = str(getattr(character, "personality", "") or "").strip()
        return "\n".join(
            line
            for line in [
                "Use case: stylized-concept",
                "Asset type: SNS reply sticker, single cute reaction stamp",
                f'Primary request: Create one chibi anime sticker of {character.name} based on the provided character base image. The sticker text must be exactly "{text}".',
                f"Character notes: {appearance[:500]}" if appearance else "",
                f"Personality notes: {personality[:300]}" if personality else "",
                "Style/medium: polished cute anime sticker illustration, clean linework, soft colors, white sticker outline, high readability at small size.",
                "Composition/framing: square canvas, one centered chibi character, waist-up or bust-up, large expressive face, simple gesture that matches the text.",
                "Lighting/mood: bright, friendly, affectionate, reply-friendly, not flashy.",
                "Text: place the exact Japanese text prominently in rounded bold lettering. Keep it legible.",
                "Constraints: preserve the character identity from the reference image; wholesome and non-sexual; modest outfit; no extra characters; no logos; no watermark.",
                f"Extra direction: {style_note[:400]}" if style_note else "",
            ]
            if line
        )

    def _store_stamp_image(self, project_id: int, character_id: int, text: str, image_bytes: bytes):
        storage_root = current_app.config.get("STORAGE_ROOT")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "assets", self.ASSET_TYPE)
        os.makedirs(output_dir, exist_ok=True)
        safe_text = "".join(char for char in text if char.isalnum())[:24] or "stamp"
        file_name = f"character_{character_id}_stamp_{safe_text}_{uuid.uuid4().hex[:10]}.png"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(image_bytes)
        return file_name, file_path

    def _serialize_stamp(self, asset):
        metadata = self._metadata(asset) or {}
        return {
            "id": asset.id,
            "asset_id": asset.id,
            "project_id": asset.project_id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "media_url": self._build_media_url(asset.file_path),
            "mime_type": asset.mime_type,
            "file_size": asset.file_size,
            "width": asset.width,
            "height": asset.height,
            "character_id": metadata.get("character_id"),
            "character_name": metadata.get("character_name"),
            "text": metadata.get("text") or asset.file_name,
            "metadata": metadata,
            "created_at": asset.created_at.isoformat() if getattr(asset, "created_at", None) else None,
            "updated_at": asset.updated_at.isoformat() if getattr(asset, "updated_at", None) else None,
        }

    def _metadata(self, asset):
        try:
            return json_util.loads(asset.metadata_json) if asset and asset.metadata_json else {}
        except Exception:
            return {}

    def _build_media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        try:
            if os.path.commonpath([normalized_path, normalized_root]) != normalized_root:
                return None
        except ValueError:
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"

    def _decode_image_base64(self, image_base64: str) -> bytes:
        try:
            return base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated stamp image payload is invalid") from exc

    def _image_dimensions(self, image_bytes: bytes, *, fallback: tuple[int | None, int | None]):
        try:
            from io import BytesIO

            with Image.open(BytesIO(image_bytes)) as image:
                return image.size
        except Exception:
            return fallback

    def _parse_size(self, size: str) -> tuple[int | None, int | None]:
        try:
            width, height = str(size).lower().split("x", 1)
            return int(width), int(height)
        except Exception:
            return None, None

    def _normalize_quality(self, value) -> str:
        value = str(value or "medium").strip().lower()
        return value if value in {"low", "medium", "high", "auto"} else "medium"

    def _normalize_size(self, value) -> str:
        value = str(value or "1024x1024").strip().lower()
        return value if value in {"1024x1024", "1536x1024", "1024x1536"} else "1024x1024"

    def _int_value(self, value) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0
