from __future__ import annotations

import base64
import binascii
import os
from datetime import datetime

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..extensions import db
from ..models.asset import Asset
from ..models.chat_session import ChatSession
from ..models.session_image import SessionImage
from ..models.story_image import StoryImage
from ..models.story_session import StorySession
from ..utils import json_util
from .asset_service import AssetService


class StudioService:
    def __init__(
        self,
        asset_service: AssetService | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._asset_service = asset_service or AssetService()
        self._image_ai_client = image_ai_client or ImageAIClient()

    def list_images(self, project_id: int, owner_user_id: int):
        images = []
        images.extend(self._list_chat_images(project_id, owner_user_id))
        images.extend(self._list_story_images(project_id, owner_user_id))
        images.extend(self._list_studio_images(project_id, owner_user_id))
        return sorted(images, key=lambda item: item.get("created_at") or "", reverse=True)

    def generate_variant(self, project_id: int, owner_user_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        try:
            source_asset_id = int(payload.get("source_asset_id") or 0)
        except (TypeError, ValueError):
            source_asset_id = 0
        if not source_asset_id:
            raise ValueError("source_asset_id is required")
        source_asset = self._asset_service.get_asset(source_asset_id)
        if not source_asset or source_asset.project_id != project_id or not getattr(source_asset, "file_path", None):
            raise ValueError("source_asset_id is invalid")
        accessible_asset_ids = {item["asset_id"] for item in self.list_images(project_id, owner_user_id)}
        if source_asset.id not in accessible_asset_ids:
            raise ValueError("source image is not available")

        instruction = str(payload.get("instruction") or "").strip()
        if not instruction:
            raise ValueError("instruction is required")
        quality = self._normalize_quality(payload.get("quality"))
        size = self._normalize_size(payload.get("size"))
        prompt = self._build_variant_prompt(instruction)
        result = self._image_ai_client.generate_image(
            prompt,
            size=size,
            quality=quality,
            output_format="png",
            background="opaque",
            input_image_paths=[source_asset.file_path],
            input_fidelity="high",
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("studio image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_image(project_id, owner_user_id, image_base64)
        width, height = self._parse_size(size)
        asset = self._asset_service.create_asset(
            project_id,
            {
                "asset_type": "studio_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "width": width,
                "height": height,
                "metadata_json": json_util.dumps(
                    {
                        "source": "studio",
                        "owner_user_id": owner_user_id,
                        "source_asset_id": source_asset.id,
                        "instruction": instruction,
                        "prompt": prompt,
                        "quality": quality,
                        "size": size,
                        "revised_prompt": result.get("revised_prompt"),
                        "generated_at": datetime.utcnow().isoformat(),
                    }
                ),
            },
        )
        return self._serialize_studio_asset(asset)

    def _list_chat_images(self, project_id: int, owner_user_id: int):
        rows = (
            db.session.query(SessionImage, ChatSession, Asset)
            .join(ChatSession, ChatSession.id == SessionImage.session_id)
            .join(Asset, Asset.id == SessionImage.asset_id)
            .filter(
                ChatSession.project_id == project_id,
                ChatSession.owner_user_id == owner_user_id,
                Asset.deleted_at.is_(None),
            )
            .order_by(SessionImage.id.desc())
            .all()
        )
        return [
            self._serialize_image(
                asset,
                source="chat",
                source_label="チャット",
                source_image_id=image.id,
                prompt_text=image.prompt_text,
                image_type=image.image_type,
                quality=image.quality,
                size=image.size,
                created_at=image.created_at,
                return_url=f"/projects/{project_id}/live-chat/{session.id}",
            )
            for image, session, asset in rows
        ]

    def _list_story_images(self, project_id: int, owner_user_id: int):
        rows = (
            db.session.query(StoryImage, StorySession, Asset)
            .join(StorySession, StorySession.id == StoryImage.session_id)
            .join(Asset, Asset.id == StoryImage.asset_id)
            .filter(
                StorySession.project_id == project_id,
                StorySession.owner_user_id == owner_user_id,
                Asset.deleted_at.is_(None),
            )
            .order_by(StoryImage.id.desc())
            .all()
        )
        return [
            self._serialize_image(
                asset,
                source="story",
                source_label="ストーリー",
                source_image_id=image.id,
                prompt_text=image.prompt_text,
                image_type=image.visual_type,
                quality=(self._load_json(image.metadata_json) or {}).get("quality"),
                size=(self._load_json(image.metadata_json) or {}).get("size"),
                created_at=image.created_at,
                return_url=f"/projects/{project_id}/story-sessions/{session.id}",
            )
            for image, session, asset in rows
        ]

    def _list_studio_images(self, project_id: int, owner_user_id: int):
        assets = Asset.query.filter(
            Asset.project_id == project_id,
            Asset.asset_type == "studio_image",
            Asset.deleted_at.is_(None),
        ).order_by(Asset.id.desc()).all()
        items = []
        for asset in assets:
            metadata = self._load_json(asset.metadata_json) or {}
            if int(metadata.get("owner_user_id") or 0) != int(owner_user_id):
                continue
            items.append(self._serialize_studio_asset(asset))
        return items

    def _serialize_studio_asset(self, asset):
        metadata = self._load_json(asset.metadata_json) or {}
        return self._serialize_image(
            asset,
            source="studio",
            source_label="スタジオ",
            source_image_id=asset.id,
            prompt_text=metadata.get("prompt") or metadata.get("instruction"),
            image_type="studio_image",
            quality=metadata.get("quality"),
            size=metadata.get("size"),
            created_at=asset.created_at,
            return_url=None,
            metadata=metadata,
        )

    def _serialize_image(
        self,
        asset,
        *,
        source: str,
        source_label: str,
        source_image_id: int,
        prompt_text: str | None,
        image_type: str | None,
        quality: str | None,
        size: str | None,
        created_at,
        return_url: str | None,
        metadata: dict | None = None,
    ):
        metadata = metadata or self._load_json(asset.metadata_json) or {}
        return {
            "id": f"{source}:{source_image_id}",
            "source": source,
            "source_label": source_label,
            "source_image_id": source_image_id,
            "asset_id": asset.id,
            "media_url": self._build_media_url(asset.file_path),
            "file_name": asset.file_name,
            "image_type": image_type,
            "prompt_text": prompt_text or metadata.get("prompt") or metadata.get("revised_prompt") or "",
            "quality": quality,
            "size": size or self._size_from_asset(asset),
            "return_url": return_url,
            "created_at": created_at.isoformat() if getattr(created_at, "isoformat", None) else None,
            "metadata": metadata,
        }

    def _build_variant_prompt(self, instruction: str):
        return "\n".join(
            [
                "参照画像を基準画像として使い、ユーザーの変更指示に従って新しい画像を生成してください。",
                "同じ人物、顔立ち、髪型、画風、質感、年齢感、身体バランスは維持する。",
                "背景、衣装、表情、ポーズ、小物、光、季節など、指示された要素だけを変える。",
                "文字、字幕、ロゴ、透かし、UI、看板の読める文字は入れない。",
                "露骨な性的描写、裸、下着、身体部位の強調は避ける。",
                f"変更指示: {instruction}",
            ]
        )

    def _store_generated_image(self, project_id: int, owner_user_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated studio image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        directory = os.path.join(storage_root, "projects", str(project_id), "generated", "studio", str(owner_user_id))
        os.makedirs(directory, exist_ok=True)
        file_name = f"studio_{timestamp}.png"
        file_path = os.path.join(directory, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)

    def _build_media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        if not normalized_path.startswith(normalized_root):
            return None
        return f"/media/{os.path.relpath(normalized_path, normalized_root).replace(os.sep, '/')}"

    def _load_json(self, value):
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json_util.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _normalize_quality(self, value):
        value = str(value or "medium").strip().lower()
        return value if value in {"low", "medium", "high"} else "medium"

    def _normalize_size(self, value):
        value = str(value or "1536x1024").strip().lower()
        return value if value in {"1024x1024", "1536x1024", "1024x1536"} else "1536x1024"

    def _parse_size(self, value):
        try:
            width, height = str(value).split("x", 1)
            return int(width), int(height)
        except Exception:
            return None, None

    def _size_from_asset(self, asset):
        if asset.width and asset.height:
            return f"{asset.width}x{asset.height}"
        return None
