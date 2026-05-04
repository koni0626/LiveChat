from __future__ import annotations

import base64
import binascii
import os
import uuid

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..repositories.asset_repository import AssetRepository
from ..repositories.character_outfit_repository import CharacterOutfitRepository
from ..repositories.character_repository import CharacterRepository
from ..utils import json_util
from .asset_service import AssetService
from .user_setting_service import UserSettingService


class ClosetService:
    def __init__(
        self,
        outfit_repository: CharacterOutfitRepository | None = None,
        character_repository: CharacterRepository | None = None,
        asset_repository: AssetRepository | None = None,
        asset_service: AssetService | None = None,
        image_ai_client: ImageAIClient | None = None,
        user_setting_service: UserSettingService | None = None,
    ):
        self._outfits = outfit_repository or CharacterOutfitRepository()
        self._characters = character_repository or CharacterRepository()
        self._assets = asset_repository or AssetRepository()
        self._asset_service = asset_service or AssetService()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._user_setting_service = user_setting_service or UserSettingService()

    def list_project_outfits(self, project_id: int) -> dict:
        characters = self._characters.list_by_project(project_id)
        for character in characters:
            self.ensure_initial_outfit(character)
        outfits = self._outfits.list_by_project(project_id)
        return {
            "characters": [self._serialize_character(character) for character in characters],
            "outfits": [self.serialize_outfit(outfit) for outfit in outfits],
        }

    def list_character_outfits(self, character_id: int) -> list[dict]:
        character = self._characters.get(character_id)
        if not character:
            raise LookupError("character not found")
        self.ensure_initial_outfit(character)
        return [self.serialize_outfit(outfit) for outfit in self._outfits.list_by_character(character_id)]

    def ensure_initial_outfit(self, character):
        if not character or not getattr(character, "base_asset_id", None):
            return None
        existing = self._outfits.list_by_character(character.id)
        initial = next(
            (
                outfit
                for outfit in existing
                if int(outfit.asset_id or 0) == int(character.base_asset_id or 0)
                and self._source_type(outfit) == "character_base"
            ),
            None,
        )
        if initial:
            return initial
        asset = self._assets.get(character.base_asset_id)
        if not asset or asset.project_id != character.project_id:
            return None
        return self._outfits.create(
            {
                "project_id": character.project_id,
                "character_id": character.id,
                "name": "基準画像",
                "description": "キャラクターの基準画像をクローゼットの初期衣装として登録したものです。",
                "asset_id": asset.id,
                "thumbnail_asset_id": asset.id,
                "source_type": "character_base",
                "tags_json": json_util.dumps(["基準画像"]),
                "usage_scene": "daily",
                "season": "all",
                "mood": None,
                "color_notes": None,
                "fixed_parts": None,
                "allowed_changes": None,
                "ng_rules": None,
                "prompt_notes": "Use this as the base character outfit reference.",
                "is_default": False,
                "status": "active",
            }
        )

    def get_outfit(self, outfit_id: int):
        return self.serialize_outfit(self._outfits.get(outfit_id))

    def resolve_outfit(self, character_id: int, outfit_id: int | None = None):
        if outfit_id:
            outfit = self._outfits.get(outfit_id)
            if outfit and outfit.character_id == character_id:
                return outfit
        return None

    def create_outfit(self, project_id: int, character_id: int, payload: dict, upload_file=None):
        character = self._characters.get(character_id)
        if not character or character.project_id != project_id:
            raise LookupError("character not found")
        asset_id = self._resolve_asset_id(project_id, payload, upload_file)
        name = str(payload.get("name") or "").strip()[:255]
        if not name:
            name = "衣装"
        normalized = self._normalize_payload(payload)
        normalized.update(
            {
                "project_id": project_id,
                "character_id": character_id,
                "name": name,
                "asset_id": asset_id,
                "thumbnail_asset_id": payload.get("thumbnail_asset_id") or asset_id,
                "source_type": self._normalize_source_type(payload.get("source_type")),
            }
        )
        outfit = self._outfits.create(normalized)
        asset = self._assets.get(asset_id)
        if asset:
            self._asset_service.update_asset(
                asset.id,
                {
                    "metadata_json": json_util.dumps(
                        {
                            "source": "closet",
                            "project_id": project_id,
                            "character_id": character_id,
                            "outfit_id": outfit.id,
                        }
                    )
                },
            )
        return self.serialize_outfit(outfit)

    def generate_outfit_image(self, project_id: int, user_id: int, character_id: int, payload: dict):
        character = self._characters.get(character_id)
        if not character or character.project_id != project_id:
            raise LookupError("character not found")
        instruction = str(payload.get("prompt_text") or payload.get("prompt") or "").strip()
        if not instruction:
            raise ValueError("prompt_text is required")

        reference_paths, reference_asset_ids = self._outfit_generation_references(character, payload)
        prompt = self._build_generation_prompt(character, instruction, payload)
        image_options = self._user_setting_service.apply_image_generation_settings(
            user_id,
            {
                "size": payload.get("size") or "1024x1536",
                "quality": payload.get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            },
        )
        result = self._image_ai_client.generate_image(
            prompt,
            size=image_options.get("size") or "1024x1536",
            quality=image_options.get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            model=image_options.get("model"),
            provider=image_options.get("provider"),
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
            output_format="png",
            background="opaque",
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("outfit image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_outfit_image(project_id, character_id, image_base64)
        asset = self._asset_service.create_asset(
            project_id,
            {
                "asset_type": "character_outfit_reference",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "closet_generation",
                        "project_id": project_id,
                        "character_id": character_id,
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "quality": result.get("quality") or image_options.get("quality"),
                        "size": image_options.get("size") or "1024x1536",
                        "aspect_ratio": result.get("aspect_ratio"),
                        "instruction": instruction,
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_asset_ids,
                    }
                ),
            },
        )
        return {
            "asset": self._serialize_asset(asset),
            "asset_id": asset.id,
            "character_id": character_id,
            "prompt_text": instruction,
            "provider": result.get("provider"),
            "model": result.get("model"),
            "reference_asset_ids": reference_asset_ids,
            "revised_prompt": result.get("revised_prompt"),
        }

    def update_outfit(self, outfit_id: int, payload: dict):
        outfit = self._outfits.get(outfit_id)
        if not outfit:
            return None
        normalized = self._normalize_payload(payload, partial=True)
        if "name" in payload:
            name = str(payload.get("name") or "").strip()[:255]
            if not name:
                raise ValueError("name is required")
            normalized["name"] = name
        if "asset_id" in payload:
            asset_id = self._resolve_asset_id(outfit.project_id, payload)
            normalized["asset_id"] = asset_id
            normalized["thumbnail_asset_id"] = int(payload.get("thumbnail_asset_id") or asset_id)
        updated = self._outfits.update(outfit_id, normalized)
        if "asset_id" in normalized:
            asset = self._assets.get(normalized["asset_id"])
            if asset:
                self._asset_service.update_asset(
                    asset.id,
                    {
                        "metadata_json": json_util.dumps(
                            {
                                "source": "closet",
                                "project_id": outfit.project_id,
                                "character_id": outfit.character_id,
                                "outfit_id": outfit.id,
                            }
                        )
                    },
                )
        return self.serialize_outfit(updated)

    def delete_outfit(self, outfit_id: int) -> bool:
        return self._outfits.delete(outfit_id)

    def _resolve_asset_id(self, project_id: int, payload: dict, upload_file=None) -> int:
        asset_id = int(payload.get("asset_id") or 0)
        if asset_id:
            asset = self._assets.get(asset_id)
            if not asset or asset.project_id != project_id:
                raise ValueError("asset not found")
            return asset.id
        if upload_file is None:
            raise ValueError("file is required")
        asset = self._asset_service.create_asset(
            project_id,
            {
                "asset_type": "character_outfit_reference",
                "upload_file": upload_file,
                "metadata_json": json_util.dumps({"source": "closet", "project_id": project_id}),
            },
        )
        return asset.id

    def _outfit_generation_references(self, character, payload: dict) -> tuple[list[str], list[int]]:
        pairs = []
        seen = set()
        edit_existing = self._to_bool(payload.get("edit_existing"))
        reference_outfit_id = int(payload.get("reference_outfit_id") or 0)
        reference_outfit = self._outfits.get(reference_outfit_id) if reference_outfit_id else None
        asset_ids = [
            getattr(reference_outfit, "asset_id", None),
            getattr(character, "base_asset_id", None),
        ] if edit_existing else [
            getattr(character, "base_asset_id", None),
            getattr(reference_outfit, "asset_id", None),
        ]
        for asset_id in asset_ids:
            if not asset_id or asset_id in seen:
                continue
            seen.add(asset_id)
            asset = self._assets.get(asset_id)
            if asset and asset.file_path and os.path.exists(asset.file_path):
                pairs.append((asset.file_path, asset.id))
        return [path for path, _asset_id in pairs], [asset_id for _path, asset_id in pairs]

    def _build_generation_prompt(self, character, instruction: str, payload: dict) -> str:
        edit_existing = self._to_bool(payload.get("edit_existing"))
        task_lines = (
            [
                "Edit the existing outfit image according to the outfit instruction.",
                "Treat the existing outfit image as the primary source image for composition, pose, current clothing, lighting, and overall impression.",
                "Apply the requested changes directly to that existing image instead of creating a completely new outfit concept.",
                "Use the base character image only to preserve identity if there is any conflict.",
            ]
            if edit_existing
            else [
                "Create a character outfit reference image for a visual novel character closet.",
                "Use the base character image as the primary and highest-priority full-body and identity reference.",
                "Use any outfit reference image only for clothing design inspiration, not for changing the face or body identity.",
            ]
        )
        return "\n".join(
            [
                *task_lines,
                "Do not use a face icon, thumbnail, avatar, or cropped portrait as a reference for this task.",
                "Preserve the exact face identity, facial proportions, eye shape, hairstyle, hair color, accessories, body impression, and art style.",
                "Change primarily the clothing and small accessories according to the outfit instruction.",
                "Show the character clearly, preferably full body or knees-up.",
                "Use a simple but attractive background that fits the character setting and world tone: soft room lighting, cyber boutique, elegant interior, city night view, garden, academy, fantasy hall, or another subtle scene implied by the profile.",
                "Do not use a plain gray background, blank wall, ID-photo backdrop, catalog sheet, or mannequin reference sheet.",
                "Keep the background secondary and not too busy so the outfit remains easy to reuse as a clothing reference.",
                "No text, no captions, no logos.",
                "Make the outfit easy to reuse as a clothing reference in later image generation.",
                "Avoid explicit nudity, sexual acts, nipples, genitals, fetish framing, transparent clothing emphasis, or hands on breasts/genitals.",
                f"Character name: {character.name or ''}",
                f"Character appearance: {character.appearance_summary or ''}",
                f"Character art style: {character.art_style or ''}",
                f"Character personality: {character.personality or ''}",
                f"Outfit instruction: {instruction}",
                f"Usage scene: {payload.get('usage_scene') or ''}",
                f"Season: {payload.get('season') or ''}",
                f"Mood: {payload.get('mood') or ''}",
                f"Fixed clothing parts: {payload.get('fixed_parts') or ''}",
                f"NG rules: {payload.get('ng_rules') or ''}",
            ]
        )

    def _store_generated_outfit_image(self, project_id: int, character_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated outfit image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "generated", "closet", str(character_id))
        os.makedirs(output_dir, exist_ok=True)
        file_name = f"outfit_{character_id}_{uuid.uuid4().hex[:12]}.png"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)

    def _normalize_payload(self, payload: dict, *, partial: bool = False) -> dict:
        fields = (
            "description",
            "source_type",
            "usage_scene",
            "season",
            "mood",
            "color_notes",
            "fixed_parts",
            "allowed_changes",
            "ng_rules",
            "prompt_notes",
            "status",
        )
        normalized = {}
        for field in fields:
            if field in payload or not partial:
                value = payload.get(field)
                normalized[field] = (
                    self._normalize_source_type(value)
                    if field == "source_type"
                    else str(value).strip() if value is not None else None
                )
        if "tags" in payload or "tags_json" in payload or not partial:
            normalized["tags_json"] = self._normalize_tags(payload)
        if "is_default" in payload or not partial:
            normalized["is_default"] = False
        return normalized

    def _normalize_tags(self, payload: dict) -> str | None:
        raw = payload.get("tags")
        if raw is None:
            raw = payload.get("tags_json")
        values = []
        if isinstance(raw, list):
            source = raw
        else:
            text = str(raw or "")
            source = text.replace(",", "\n").splitlines()
        seen = set()
        for item in source:
            text = str(item or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            values.append(text[:80])
        return json_util.dumps(values) if values else None

    def _normalize_source_type(self, value) -> str:
        source_type = str(value or "outfit").strip().lower()
        return source_type if source_type in {"outfit", "character_base"} else "outfit"

    def _source_type(self, outfit) -> str:
        return self._normalize_source_type(getattr(outfit, "source_type", None))

    def _to_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def serialize_outfit(self, outfit) -> dict | None:
        if not outfit:
            return None
        asset = self._assets.get(outfit.asset_id) if outfit.asset_id else None
        thumbnail = self._assets.get(outfit.thumbnail_asset_id) if outfit.thumbnail_asset_id else asset
        return {
            "id": outfit.id,
            "project_id": outfit.project_id,
            "character_id": outfit.character_id,
            "name": outfit.name,
            "description": outfit.description,
            "asset": self._serialize_asset(asset),
            "thumbnail_asset": self._serialize_asset(thumbnail),
            "source_type": self._source_type(outfit),
            "tags": self._load_list(outfit.tags_json),
            "usage_scene": outfit.usage_scene,
            "season": outfit.season,
            "mood": outfit.mood,
            "color_notes": outfit.color_notes,
            "fixed_parts": outfit.fixed_parts,
            "allowed_changes": outfit.allowed_changes,
            "ng_rules": outfit.ng_rules,
            "prompt_notes": outfit.prompt_notes,
            "is_default": bool(outfit.is_default),
            "status": outfit.status,
            "created_at": outfit.created_at.isoformat() if outfit.created_at else None,
            "updated_at": outfit.updated_at.isoformat() if outfit.updated_at else None,
        }

    def outfit_prompt_lines(self, outfit) -> list[str]:
        if not outfit:
            return []
        lines = [
            "Use the selected outfit reference as the highest-priority clothing reference.",
            "Preserve the exact clothing design, silhouette, fabric impression, color palette, accessories, and distinctive details.",
            "Do not replace the outfit with a different costume unless explicitly requested.",
            f"Selected outfit name: {outfit.name or ''}",
        ]
        for label, value in (
            ("Outfit description", outfit.description),
            ("Fixed clothing parts", outfit.fixed_parts),
            ("Allowed clothing changes", outfit.allowed_changes),
            ("Outfit NG rules", outfit.ng_rules),
            ("Outfit prompt notes", outfit.prompt_notes),
        ):
            if value:
                lines.append(f"{label}: {value}")
        return lines

    def _serialize_character(self, character) -> dict | None:
        if not character:
            return None
        return {
            "id": character.id,
            "project_id": character.project_id,
            "name": character.name,
            "nickname": character.nickname,
        }

    def _serialize_asset(self, asset) -> dict | None:
        if not asset:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "mime_type": asset.mime_type,
            "media_url": self._media_url(asset.file_path),
            "width": asset.width,
            "height": asset.height,
        }

    def _media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        if not storage_root:
            return None
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        try:
            if os.path.commonpath([normalized_path, normalized_root]) != normalized_root:
                return None
        except ValueError:
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"

    def _load_list(self, raw_value) -> list[str]:
        if not raw_value:
            return []
        try:
            parsed = json_util.loads(raw_value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
