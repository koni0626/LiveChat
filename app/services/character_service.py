import base64
import binascii
import io
import os
from datetime import datetime

from flask import current_app
from PIL import Image

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

    def create_character(self, project_id: int, payload: dict, *, created_by_user_id: int | None = None):
        character = self._repo.create(project_id, payload)
        if not payload.get("thumbnail_asset_id"):
            try:
                character = self._refresh_thumbnail(character)
            except Exception:
                current_app.logger.exception("character portrait generation failed during character creation")
        if created_by_user_id:
            try:
                self._ensure_default_live_chat_room(character, created_by_user_id=created_by_user_id)
            except Exception:
                current_app.logger.exception("default live chat room creation failed during character creation")
        return self.get_character(character.id)

    def get_character(self, character_id: int, include_deleted: bool = False):
        return self._repo.get(character_id, include_deleted=include_deleted)

    def update_character(self, character_id: int, payload: dict):
        character = self._repo.update(character_id, payload)
        if character and "base_asset_id" in payload and self._can_refresh_thumbnail(character):
            try:
                character = self._refresh_thumbnail(character)
            except Exception:
                current_app.logger.exception("character portrait generation failed during character update")
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
            model=payload.get("model") or payload.get("image_ai_model"),
            provider=payload.get("provider") or payload.get("image_ai_provider"),
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
            try:
                self._refresh_thumbnail(character, payload=payload)
            except Exception:
                current_app.logger.exception("character portrait generation failed after base image generation")
        return self.get_character(character.id)

    def generate_portrait_image(self, character_id: int, payload: dict | None = None):
        character = self.get_character(character_id)
        if not character:
            return None
        character = self._refresh_thumbnail(character, payload=payload)
        return self.get_character(character.id)

    def generate_introduction_text(self, character_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        character = self.get_character(character_id)
        if not character:
            return None
        prompt = self._build_introduction_prompt(character, payload)
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.75,
            max_tokens=700,
        )
        text = self._normalize_generated_introduction(result.get("text"))
        if not text:
            raise RuntimeError("introduction generation response is empty")
        return self._repo.update(character.id, {"introduction_text": text})

    def generate_bromide_image(self, character_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        character = self.get_character(character_id)
        if not character:
            return None
        reference_paths, reference_asset_ids = self._character_reference_image_paths(character)
        prompt = self._build_bromide_image_prompt(character, has_reference=bool(reference_paths), payload=payload)
        generation_size = payload.get("size") or "1024x1536"
        result = self._image_ai_client.generate_image(
            prompt,
            size=generation_size,
            quality=payload.get("quality") or "medium",
            model=payload.get("model") or payload.get("image_ai_model"),
            provider=payload.get("provider") or payload.get("image_ai_provider"),
            output_format="png",
            background="opaque",
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("bromide image generation response did not include image_base64")
        file_name, file_path, file_size, width, height = self._store_generated_bromide_image(
            project_id=character.project_id,
            character_id=character.id,
            image_base64=image_base64,
        )
        asset = self._asset_service.create_asset(
            character.project_id,
            {
                "asset_type": "character_bromide",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "width": width,
                "height": height,
                "metadata_json": json_util.dumps(
                    {
                        "source": "character_bromide_generation",
                        "character_id": character.id,
                        "reference_asset_ids": reference_asset_ids,
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "model": result.get("model"),
                        "quality": result.get("quality"),
                        "size": generation_size,
                        "final_aspect_ratio": "3:4",
                        "reference_image_count": result.get("reference_image_count") or len(reference_paths),
                        "operation": result.get("operation"),
                    }
                ),
            },
        )
        self._repo.update(character.id, {"bromide_asset_id": asset.id})
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

    def _refresh_thumbnail(self, character, payload: dict | None = None):
        thumbnail = self._thumbnail_service.generate_for_character(character, payload=payload)
        if thumbnail:
            character = self._repo.update(character.id, {"thumbnail_asset_id": thumbnail.id})
        return character

    def _ensure_default_live_chat_room(self, character, *, created_by_user_id: int):
        if not character:
            return None
        from .live_chat_room_service import LiveChatRoomService

        room_service = LiveChatRoomService(character_service=self)
        existing = room_service.get_room_by_character(character.id)
        if existing:
            return existing
        return room_service.create_room(
            character.project_id,
            self._build_default_live_chat_room_payload(character),
            created_by_user_id=created_by_user_id,
        )

    def _build_default_live_chat_room_payload(self, character) -> dict:
        name = str(getattr(character, "name", None) or "このキャラクター").strip()
        nickname = str(getattr(character, "nickname", None) or "").strip()
        title_name = nickname or name
        description_parts = [f"{title_name}と1対1で会話するための自動作成ルームです。"]
        if getattr(character, "character_summary", None):
            description_parts.append(self._shorten_for_prompt(character.character_summary, limit=120))

        objective_lines = [
            f"# {title_name}の会話目的",
            "",
            "## このルームの役割",
            f"- {name}が、プレイヤーと継続的に1対1で話すための専用ルームとして振る舞う。",
            "- 単なる案内役ではなく、キャラクター自身の価値観、欲求、弱点、距離感を持った相手として会話する。",
            "- プレイヤーの発言を受け流さず、感情・意図・前回までの文脈を拾って、関係が少しずつ進むように返答する。",
            "",
            "## 会話で目指すこと",
            "- プレイヤーが「このキャラクターと話している」と感じられる口調、反応、間、言葉選びを維持する。",
            "- 雑談、相談、軽いからかい、好意、距離を詰める会話を、キャラクター設定に沿って自然に展開する。",
            "- すぐに結論を出さず、相手に質問を返し、気になった点を掘り下げ、次の会話につながる小さな未解決を残す。",
            "- プレイヤーを中心にしすぎず、キャラクター自身の都合、好き嫌い、こだわり、隠したい本音も会話に混ぜる。",
            "",
            "## キャラクターとして守ること",
        ]
        profile_lines = self._character_profile_lines_for_room(character)
        objective_lines.extend(profile_lines or ["- 入力されているキャラクター設定を最優先し、設定にないことは急に断定しない。"])
        objective_lines.extend(
            [
                "",
                "## 口調と一人称",
                f"- 一人称: {getattr(character, 'first_person', None) or 'キャラクター設定に従う'}",
                f"- プレイヤーの呼び方: {getattr(character, 'second_person', None) or '会話の流れに合わせる'}",
                "- セリフは説明文になりすぎないようにし、短い反応、含みのある一言、質問を混ぜる。",
                "",
                "## 避けること",
                "- キャラクター設定と矛盾する性格・口調・過去・関係性を勝手に追加しない。",
                "- 何でも肯定するだけの反応にしない。嫌なこと、困ること、照れること、距離を置くことも自然に表現する。",
                "- システム都合やAIであることをキャラクター本人の発言として出さない。",
            ]
        )
        if getattr(character, "ng_rules", None):
            objective_lines.extend(["", "## 固有のNGルール", str(character.ng_rules).strip()])

        proxy_objective = "\n".join(
            [
                "# 代理プレイヤーの目的",
                "",
                f"- {title_name}に興味を持ち、自然な会話を通して相手のことを知ろうとする。",
                "- 最初から過度に踏み込まず、相手の反応を見ながら距離を調整する。",
                "- 相手の好きなもの、苦手なもの、価値観、隠している本音を少しずつ引き出す。",
                "- 会話が止まったときは、直前の話題・相手の設定・その場の感情から自然に次の質問を作る。",
            ]
        )
        return {
            "title": f"{title_name}のルーム",
            "description": " ".join(description_parts),
            "character_id": character.id,
            "conversation_objective": "\n".join(objective_lines),
            "proxy_player_objective": proxy_objective,
            "proxy_player_gender": "",
            "proxy_player_speech_style": "自然体で、相手の口調や距離感に合わせる。急に馴れ馴れしくしすぎず、会話が進むほど少しずつ踏み込む。",
            "status": "published",
            "sort_order": 0,
        }

    def build_default_live_chat_room_payload(self, character) -> dict:
        return self._build_default_live_chat_room_payload(character)

    def _character_profile_lines_for_room(self, character) -> list[str]:
        lines = []
        field_map = [
            ("概要", getattr(character, "character_summary", None)),
            ("性格", getattr(character, "personality", None)),
            ("話し方", getattr(character, "speech_style", None)),
            ("セリフ例", getattr(character, "speech_sample", None)),
            ("見た目", getattr(character, "appearance_summary", None)),
            ("会話メモ", getattr(character, "memory_notes", None)),
        ]
        for label, value in field_map:
            text = self._shorten_for_prompt(value, limit=700)
            if text:
                lines.append(f"- {label}: {text}")
        try:
            profile = json_util.loads(character.memory_profile_json) if character.memory_profile_json else {}
        except Exception:
            profile = {}
        if isinstance(profile, dict):
            list_fields = [
                ("好きなもの", profile.get("likes")),
                ("嫌いなもの", profile.get("dislikes")),
                ("趣味", profile.get("hobbies")),
                ("苦手・地雷", profile.get("taboos")),
                ("印象的な出来事", profile.get("memorable_events")),
            ]
            romance = profile.get("romance_preferences") or {}
            if isinstance(romance, dict):
                list_fields.extend(
                    [
                        ("好む距離の詰め方", romance.get("favorite_approach")),
                        ("苦手な距離の詰め方", romance.get("avoid_approach")),
                        ("刺さるポイント", romance.get("attraction_points")),
                        ("越えてはいけない境界", romance.get("boundaries")),
                    ]
                )
            for label, values in list_fields:
                if isinstance(values, list) and values:
                    text = " / ".join(str(item).strip() for item in values if str(item).strip())
                    if text:
                        lines.append(f"- {label}: {self._shorten_for_prompt(text, limit=300)}")
        return lines

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
        if getattr(character, "character_summary", None):
            parts.append(f"Character overview and concept: {character.character_summary}")
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

    def _build_introduction_prompt(self, character, payload: dict) -> str:
        world = self._world_service.get_world(character.project_id)
        lines = [
            "日本語で、キャラクター本人が初対面の相手に向けて話す自己紹介文を作成してください。",
            "用途はキャラクター一覧とライブチャット開始前のプロフィールです。",
            "一人称、口調、距離感、価値観をキャラクター設定に合わせてください。",
            "長さは180〜320字程度。説明臭くしすぎず、会話したくなる余白を残してください。",
            "箇条書き、Markdown、見出し、引用符、前置きは禁止。本文だけを返してください。",
            "",
            f"名前: {character.name}",
        ]
        field_map = [
            ("あだ名", getattr(character, "nickname", None)),
            ("性別", getattr(character, "gender", None)),
            ("年齢印象", getattr(character, "age_impression", None)),
            ("一人称", getattr(character, "first_person", None)),
            ("相手の呼び方", getattr(character, "second_person", None)),
            ("概要", getattr(character, "character_summary", None)),
            ("性格", getattr(character, "personality", None)),
            ("話し方", getattr(character, "speech_style", None)),
            ("セリフ例", getattr(character, "speech_sample", None)),
            ("見た目", getattr(character, "appearance_summary", None)),
            ("NGルール", getattr(character, "ng_rules", None)),
        ]
        for label, value in field_map:
            text = self._shorten_for_prompt(value, limit=700)
            if text:
                lines.append(f"{label}: {text}")
        if world:
            lines.extend(
                [
                    "",
                    "世界観:",
                    f"世界名: {getattr(world, 'name', '') or ''}",
                    f"雰囲気: {getattr(world, 'tone', '') or ''}",
                    f"概要: {self._shorten_for_prompt(getattr(world, 'overview', None), limit=600)}",
                ]
            )
        if payload.get("direction"):
            lines.extend(["", f"追加方針: {self._shorten_for_prompt(payload.get('direction'), limit=500)}"])
        return "\n".join(lines)

    def _normalize_generated_introduction(self, value) -> str:
        text = str(value or "").strip()
        text = text.replace("\r\n", "\n").strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines).strip()
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("「") and text.endswith("」")):
            text = text[1:-1].strip()
        return text[:1000]

    def _character_reference_image_paths(self, character) -> tuple[list[str], list[int]]:
        reference_paths = []
        reference_asset_ids = []
        for asset_id in (getattr(character, "base_asset_id", None), getattr(character, "thumbnail_asset_id", None)):
            if not asset_id or asset_id in reference_asset_ids:
                continue
            asset = self._asset_service.get_asset(asset_id)
            if asset and getattr(asset, "file_path", None) and os.path.exists(asset.file_path):
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)
        return reference_paths[:2], reference_asset_ids[:2]

    def _build_bromide_image_prompt(self, character, *, has_reference: bool, payload: dict) -> str:
        art_style = str(payload.get("art_style") or getattr(character, "art_style", None) or "").strip()
        parts = [
            "Create a glamorous 3:4 character bromide portrait for a Japanese visual novel / live chat character.",
            "This is a premium collectible profile image, not a plain ID icon. Make it visually striking, polished, and memorable.",
            "Show exactly one character. Use a vertical composition with the face clearly readable and the upper body or full figure attractively staged.",
            "Use cinematic lighting, a charming pose, expressive eyes, and a background motif that supports the character concept.",
            "No text, no words, no letters, no subtitles, no captions, no speech bubbles, no readable signs, no UI overlay, no watermark, no logo.",
            "Final image will be cropped to a 3:4 aspect ratio, so keep the character centered with safe margins around the head and body.",
            f"Name: {character.name}",
        ]
        if has_reference:
            parts.append(
                "Use the provided reference image as the primary identity reference. Preserve the same character, face impression, hairstyle, body impression, outfit motifs, color palette, and art style."
            )
        field_map = [
            ("Nickname", getattr(character, "nickname", None)),
            ("Gender", getattr(character, "gender", None)),
            ("Age impression", getattr(character, "age_impression", None)),
            ("First person", getattr(character, "first_person", None)),
            ("How they call the player", getattr(character, "second_person", None)),
            ("Character overview and concept", getattr(character, "character_summary", None)),
            ("Appearance", getattr(character, "appearance_summary", None)),
            ("Personality", getattr(character, "personality", None)),
            ("Speech style", getattr(character, "speech_style", None)),
            ("Sample lines", getattr(character, "speech_sample", None)),
            ("Self introduction", getattr(character, "introduction_text", None)),
            ("Do not violate these character rules", getattr(character, "ng_rules", None)),
        ]
        for label, value in field_map:
            text = self._shorten_for_prompt(value, limit=800)
            if text:
                parts.append(f"{label}: {text}")
        if art_style:
            parts.append(f"Art style: {art_style}")
        else:
            parts.append("Art style: high-quality Japanese anime visual novel key art, consistent linework and colors.")
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
            "Required JSON keys: name, nickname, gender, age_impression, first_person, second_person, character_summary, appearance_summary, art_style, personality, likes_text, dislikes_text, hobbies_text, taboos_text, romance_favorite_approach_text, romance_avoid_approach_text, romance_attraction_points_text, romance_boundaries_text, memorable_events_text, memory_notes, speech_style, speech_sample, ng_rules.",
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
                        f"  character_summary: {self._shorten_for_prompt(getattr(character, 'character_summary', None))}",
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
            "character_summary",
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

    def _store_generated_bromide_image(self, *, project_id: int, character_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated bromide image payload is invalid") from exc
        output_dir = self._build_bromide_output_directory(project_id)
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_name = f"character_{character_id}_bromide_{timestamp}.png"
        file_path = os.path.join(output_dir, file_name)
        with Image.open(io.BytesIO(raw_bytes)) as image:
            canvas = self._crop_image_to_three_by_four(image.convert("RGB"))
            canvas.save(file_path, "PNG", optimize=True)
        file_size = os.path.getsize(file_path)
        with Image.open(file_path) as stored:
            width, height = stored.size
        return file_name, file_path, file_size, width, height

    def _crop_image_to_three_by_four(self, image: Image.Image) -> Image.Image:
        width, height = image.size
        target_ratio = 3 / 4
        current_ratio = width / height if height else target_ratio
        if current_ratio > target_ratio:
            new_width = int(round(height * target_ratio))
            left = max(0, (width - new_width) // 2)
            box = (left, 0, left + new_width, height)
        else:
            new_height = int(round(width / target_ratio))
            top = max(0, int(round((height - new_height) * 0.42)))
            box = (0, top, width, top + new_height)
        cropped = image.crop(box)
        return cropped.resize((960, 1280), Image.Resampling.LANCZOS)

    def _build_bromide_output_directory(self, project_id: int) -> str:
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        return os.path.join(storage_root, "projects", str(project_id), "assets", "character_bromide")
