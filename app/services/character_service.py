import base64
import binascii
import os
from datetime import datetime

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..repositories.character_repository import CharacterRepository
from ..utils import json_util
from .character_thumbnail_service import CharacterThumbnailService
from .asset_service import AssetService
from .world_service import WorldService


class CharacterService:
    def __init__(
        self,
        repository: CharacterRepository | None = None,
        thumbnail_service: CharacterThumbnailService | None = None,
        asset_service: AssetService | None = None,
        image_ai_client: ImageAIClient | None = None,
        text_ai_client: TextAIClient | None = None,
        world_service: WorldService | None = None,
    ):
        self._repo = repository or CharacterRepository()
        self._thumbnail_service = thumbnail_service or CharacterThumbnailService()
        self._asset_service = asset_service or AssetService()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._world_service = world_service or WorldService()

    def list_characters(self, project_id: int, include_deleted: bool = False):
        return self._repo.list_by_project(project_id, include_deleted=include_deleted)

    def create_character(self, project_id: int, payload: dict):
        character = self._repo.create(project_id, payload)
        if payload.get("base_asset_id") and not payload.get("thumbnail_asset_id"):
            self._refresh_thumbnail(character)
        return character

    def get_character(self, character_id: int, include_deleted: bool = False):
        return self._repo.get(character_id, include_deleted=include_deleted)

    def update_character(self, character_id: int, payload: dict):
        character = self._repo.update(character_id, payload)
        if character and "base_asset_id" in payload and self._can_refresh_thumbnail(character):
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
        resolved_art_style = str(payload.get("art_style") or getattr(character, "art_style", None) or "").strip()
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
                        "art_style": resolved_art_style,
                    }
                ),
            },
        )
        update_payload = {"base_asset_id": asset.id}
        if resolved_art_style:
            update_payload["art_style"] = resolved_art_style
        character = self._repo.update(character.id, update_payload)
        if self._can_refresh_thumbnail(character):
            self._refresh_thumbnail(character)
        return self.get_character(character.id)

    def generate_character_draft(self, project_id: int, payload: dict | None = None) -> dict:
        payload = dict(payload or {})
        world = self._world_service.get_world(project_id)
        if not self._world_service.has_usable_world(project_id):
            raise ValueError("先に世界観設定を入力してください。キャラクターは世界観をベースに仮入力します。")

        existing_characters = self.list_characters(project_id)
        prompt = self._build_character_draft_prompt(world, payload, existing_characters)
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.85,
            response_format={"type": "json_object"},
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("character draft response is invalid")
        return self._normalize_character_draft(parsed)

    def _refresh_thumbnail(self, character):
        thumbnail = self._thumbnail_service.generate_for_character(character)
        if thumbnail:
            character = self._repo.update(character.id, {"thumbnail_asset_id": thumbnail.id})
        return character

    def _can_refresh_thumbnail(self, character) -> bool:
        thumbnail_asset_id = getattr(character, "thumbnail_asset_id", None)
        if not thumbnail_asset_id:
            return True
        thumbnail = self._asset_service.get_asset(thumbnail_asset_id)
        return getattr(thumbnail, "asset_type", None) == "character_thumbnail"

    def _build_base_image_prompt(self, character, payload: dict) -> str:
        art_style = str(payload.get("art_style") or getattr(character, "art_style", None) or "").strip()
        parts = [
            "Create a full-body character reference image for a visual novel / live chat character.",
            "Show exactly one character, full body, standing pose, clear face, clear outfit, centered composition.",
            "No text, no words, no letters, no subtitles, no captions, no speech bubbles, no readable signs, no UI overlay, no watermark, no logo.",
            "Use a clean character design sheet feel, but make it attractive and polished.",
            f"Name: {character.name}",
        ]
        if getattr(character, "nickname", None):
            parts.append(f"Nickname: {character.nickname}")
        if getattr(character, "gender", None):
            parts.append(f"Gender: {character.gender}")
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

    def _build_character_draft_prompt(self, world, payload: dict, existing_characters=None) -> str:
        current = payload.get("current_character") if isinstance(payload.get("current_character"), dict) else payload
        current_name = str((current or {}).get("name") or "").strip()
        existing_characters = [
            character
            for character in (existing_characters or [])
            if not current_name or str(character.name or "").strip() != current_name
        ]
        lines = [
            "Return only JSON.",
            "Create a draft character for a Japanese character live chat tool.",
            "The character must fit the given world setting and be engaging in one-on-one conversation.",
            "Do not create a generic guide. The character should have personal motives, preferences, voice, and boundaries.",
            "Avoid overlap with existing characters in the same project.",
            "Do not reuse existing character names, nicknames, visual motifs, personality archetypes, speech style, romantic preferences, or conversation role.",
            "If the world already has several characters, create a new contrastive character who expands the cast dynamics.",
            "Required JSON keys: name, nickname, gender, age_impression, first_person, second_person, appearance_summary, art_style, personality, likes_text, dislikes_text, hobbies_text, taboos_text, romance_favorite_approach_text, romance_avoid_approach_text, romance_attraction_points_text, romance_boundaries_text, memorable_events_text, memory_notes, speech_style, speech_sample, ng_rules.",
            "All values must be Japanese strings. Long fields should be Markdown-friendly with bullet lists where useful.",
            "",
            "World setting:",
            f"name: {world.name or ''}",
            f"tone: {world.tone or ''}",
            f"era: {world.era_description or ''}",
            f"place: {world.overview or ''}",
            f"technology: {world.technology_level or ''}",
            f"social_structure: {world.social_structure or ''}",
            f"important_facilities: {world.rules_json or ''}",
            f"forbidden_settings: {world.forbidden_json or ''}",
        ]
        if existing_characters:
            lines.extend(["", "Existing characters to avoid duplicating:"])
            for character in existing_characters[:30]:
                lines.extend(
                    [
                        f"- name: {character.name or ''}",
                        f"  nickname: {character.nickname or ''}",
                        f"  gender: {character.gender or ''}",
                        f"  age_impression: {character.age_impression or ''}",
                        f"  first_person: {character.first_person or ''}",
                        f"  second_person: {character.second_person or ''}",
                        f"  appearance_summary: {self._shorten_for_prompt(character.appearance_summary)}",
                        f"  personality: {self._shorten_for_prompt(character.personality)}",
                        f"  speech_style: {self._shorten_for_prompt(character.speech_style)}",
                        f"  speech_sample: {self._shorten_for_prompt(character.speech_sample)}",
                    ]
                )
        if current:
            lines.append("")
            lines.append("Current form input. Respect filled values when they are useful, and complete empty fields:")
            for key, value in current.items():
                lines.append(f"{key}: {value or ''}")
        return "\n".join(lines)

    def _shorten_for_prompt(self, value, limit: int = 500) -> str:
        text = str(value or "").strip().replace("\r\n", "\n")
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def _normalize_character_draft(self, parsed: dict) -> dict:
        fields = (
            "name",
            "nickname",
            "gender",
            "age_impression",
            "first_person",
            "second_person",
            "appearance_summary",
            "art_style",
            "personality",
            "likes_text",
            "dislikes_text",
            "hobbies_text",
            "taboos_text",
            "romance_favorite_approach_text",
            "romance_avoid_approach_text",
            "romance_attraction_points_text",
            "romance_boundaries_text",
            "memorable_events_text",
            "memory_notes",
            "speech_style",
            "speech_sample",
            "ng_rules",
        )
        return {field: str(parsed.get(field) or "").strip() for field in fields}

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
