import base64
import binascii
import os
from datetime import datetime

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..repositories.character_repository import CharacterRepository
from ..utils import json_util
from .character_thumbnail_service import CharacterThumbnailService


class CharacterService:
    def __init__(
        self,
        repository: CharacterRepository | None = None,
        thumbnail_service: CharacterThumbnailService | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._repo = repository or CharacterRepository()
        self._thumbnail_service = thumbnail_service or CharacterThumbnailService()
        self._image_ai_client = image_ai_client or ImageAIClient()

    def list_characters(self, project_id: int, include_deleted: bool = False):
        return self._repo.list_by_project(project_id, include_deleted=include_deleted)

    def create_character(self, project_id: int, payload: dict):
        character = self._repo.create(project_id, payload)
        if payload.get("base_asset_id"):
            self._refresh_thumbnail(character)
        return character

    def get_character(self, character_id: int, include_deleted: bool = False):
        return self._repo.get(character_id, include_deleted=include_deleted)

    def update_character(self, character_id: int, payload: dict):
        character = self._repo.update(character_id, payload)
        if character and "base_asset_id" in payload:
            self._refresh_thumbnail(character)
        return character

    def delete_character(self, character_id: int):
        return self._repo.delete(character_id)

    def restore_character(self, character_id: int):
        return self._repo.restore(character_id)

    def generate_base_image(self, character_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        character = self.get_character(character_id)
        if not character:
            return None
        prompt = self._build_base_image_prompt(character, payload)
        result = self._image_ai_client.generate_image(
            prompt,
            size=payload.get("size") or "1024x1536",
            quality=payload.get("quality") or "medium",
            output_format="png",
            background="opaque",
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_base_image(
            project_id=character.project_id,
            character_id=character.id,
            image_base64=image_base64,
        )
        from .asset_service import AssetService

        asset = AssetService().create_asset(
            character.project_id,
            {
                "asset_type": "reference_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "character_base_image_generation",
                        "character_id": character.id,
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "model": result.get("model"),
                        "quality": result.get("quality"),
                        "size": payload.get("size") or "1024x1536",
                        "art_style": payload.get("art_style"),
                    }
                ),
            },
        )
        character = self._repo.update(character.id, {"base_asset_id": asset.id})
        self._refresh_thumbnail(character)
        return self.get_character(character.id)

    def _refresh_thumbnail(self, character):
        thumbnail = self._thumbnail_service.generate_for_character(character)
        if thumbnail:
            character = self._repo.update(character.id, {"thumbnail_asset_id": thumbnail.id})
        return character

    def _build_base_image_prompt(self, character, payload: dict) -> str:
        art_style = str(payload.get("art_style") or "").strip()
        parts = [
            "Create a full-body character reference image for a visual novel / live chat character.",
            "Show exactly one character, full body, standing pose, clear face, clear outfit, centered composition.",
            "No text, no subtitles, no speech bubbles, no watermark, no logo.",
            "Use a clean character design sheet feel, but make it attractive and polished.",
            f"Name: {character.name}",
        ]
        if getattr(character, "nickname", None):
            parts.append(f"Nickname: {character.nickname}")
        if getattr(character, "age_impression", None):
            parts.append(f"Age impression: {character.age_impression}")
        if getattr(character, "first_person", None):
            parts.append(f"First person: {character.first_person}")
        if getattr(character, "second_person", None):
            parts.append(f"How they call the player: {character.second_person}")
        if getattr(character, "appearance_summary", None):
            parts.append(f"Appearance: {character.appearance_summary}")
        if getattr(character, "personality", None):
            parts.append(f"Personality: {character.personality}")
        if getattr(character, "speech_style", None):
            parts.append(f"Speech style: {character.speech_style}")
        if getattr(character, "ng_rules", None):
            parts.append(f"Do not violate these character rules: {character.ng_rules}")
        if art_style:
            parts.append(f"Art style: {art_style}")
        else:
            parts.append("Art style: high-quality Japanese anime visual novel character art, consistent linework and colors.")
        parts.append("Background: simple neutral studio background so the character design is easy to reuse as a reference image.")
        return "\n".join(parts)

    def _store_generated_base_image(self, *, project_id: int, character_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "assets", "reference_image")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_name = f"character_{character_id}_base_{timestamp}.png"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)
