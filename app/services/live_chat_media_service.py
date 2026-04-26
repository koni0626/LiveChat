from __future__ import annotations

import os
from typing import Callable

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..utils import json_util
from . import live_chat_image_support as image_support
from . import live_chat_prompt_support as prompt_support
from . import live_chat_text_support as text_support
from .asset_service import AssetService
from .chat_session_service import ChatSessionService
from .session_image_service import SessionImageService
from .session_state_service import SessionStateService


class LiveChatMediaService:
    """Image and costume operations for live chat sessions."""

    def __init__(
        self,
        *,
        chat_session_service: ChatSessionService,
        session_state_service: SessionStateService,
        session_image_service: SessionImageService,
        asset_service: AssetService,
        text_ai_client: TextAIClient,
        image_ai_client: ImageAIClient,
        context_provider: Callable[[int], dict],
        select_characters: Callable[[int], list[dict]],
    ):
        self._chat_session_service = chat_session_service
        self._session_state_service = session_state_service
        self._session_image_service = session_image_service
        self._asset_service = asset_service
        self._text_ai_client = text_ai_client
        self._image_ai_client = image_ai_client
        self._context_provider = context_provider
        self._select_characters = select_characters

    def _load_json(self, value):
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

    def _serialize_asset(self, asset):
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
            "media_url": self._build_media_url(asset.file_path),
        }

    def serialize_session_image(self, row):
        if not row:
            return None
        asset = self._asset_service.get_asset(row.asset_id)
        return {
            "id": row.id,
            "session_id": row.session_id,
            "asset_id": row.asset_id,
            "owner_user_id": getattr(row, "owner_user_id", None),
            "character_id": getattr(row, "character_id", None),
            "linked_from_image_id": getattr(row, "linked_from_image_id", None),
            "image_type": row.image_type,
            "prompt_text": row.prompt_text,
            "state_json": self._load_json(row.state_json),
            "quality": row.quality,
            "size": row.size,
            "is_selected": bool(row.is_selected),
            "is_reference": bool(getattr(row, "is_reference", 0)),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "asset": self._serialize_asset(asset),
        }

    def _resolve_costume_library_keys(self, session_id: int, context: dict | None = None):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return {}
        character = None
        if context:
            character = self._resolve_target_character(context)
        if not character:
            characters = self._select_characters(session_id)
            character = characters[0] if characters else None
        return {
            "owner_user_id": session.owner_user_id,
            "character_id": character.get("id") if character else None,
        }

    def collect_session_reference_assets(self, session_id: int, active_characters: list[dict], *, limit: int = 1):
        selected_costume = self._session_image_service.get_selected_costume(session_id)
        reference_paths = []
        reference_asset_ids = []
        if selected_costume:
            asset = self._asset_service.get_asset(selected_costume.asset_id)
            if asset and getattr(asset, "file_path", None):
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)
        if reference_paths:
            return reference_paths, reference_asset_ids
        return image_support.collect_reference_assets(active_characters, limit=limit)

    def ensure_initial_costume(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        existing = self._session_image_service.list_costumes(session_id)
        if existing:
            return self.serialize_session_image(next((item for item in existing if item.is_selected), existing[0]))
        characters = self._select_characters(session_id)
        character = characters[0] if characters else None
        base_asset = (character or {}).get("base_asset") or {}
        asset_id = base_asset.get("id")
        if not asset_id:
            return None
        row = self._session_image_service.create_session_image(
            session_id,
            {
                "asset_id": asset_id,
                **self._resolve_costume_library_keys(session_id),
                "image_type": "costume_initial",
                "prompt_text": "キャラクター設定の基準画像",
                "state_json": {"source": "character_base_asset", "character_id": character.get("id")},
                "quality": "source",
                "size": "source",
                "is_selected": 1,
                "is_reference": 0,
            },
        )
        return self.serialize_session_image(row)

    def analyze_displayed_image(self, file_path: str, *, prompt: str | None = None, source: str = "generated_image"):
        analysis_prompt = (
            "Return only JSON. Analyze this generated visual novel image so the chat character can understand "
            "what is currently shown on screen. Required keys: location, background, visible_characters, "
            "character_poses, character_expressions, mood, time_of_day, notable_objects, short_summary, "
            "conversation_context_hint. Use concise Japanese strings. visible_characters, notable_objects must be arrays. "
            "If the image contains ocean, beach, harbor, shop interior, city street, room, sky, or similar background, "
            "state it clearly in location/background. Do not infer from the prompt alone; describe what is visible."
        )
        result = self._text_ai_client.analyze_image(file_path, prompt=analysis_prompt)
        parsed = result.get("parsed_json") or {}
        if not isinstance(parsed, dict):
            parsed = {}
        parsed.setdefault("location", None)
        parsed.setdefault("background", None)
        parsed.setdefault("visible_characters", [])
        parsed.setdefault("character_poses", None)
        parsed.setdefault("character_expressions", None)
        parsed.setdefault("mood", None)
        parsed.setdefault("time_of_day", None)
        parsed.setdefault("notable_objects", [])
        parsed.setdefault("short_summary", None)
        parsed.setdefault("conversation_context_hint", None)
        parsed["source"] = source
        parsed["image_prompt"] = prompt
        return parsed

    def _storage_root(self):
        try:
            return current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        except RuntimeError:
            return os.path.join(os.getcwd(), "storage")

    def _apply_observation_to_state(self, state_json: dict, observation: dict):
        state_json["displayed_image_observation"] = observation
        for key in ("location", "background", "mood", "time_of_day"):
            if observation.get(key):
                state_json[key] = observation[key]
        if observation.get("short_summary"):
            state_json["focus_summary"] = observation["short_summary"]

    def generate_image(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        context = self._context_provider(session_id)
        state = context["state"]
        state_json = dict(state.get("state_json") or {})
        conversation_prompt = image_support.generate_japanese_conversation_image_prompt(self._text_ai_client, context, state)
        state_json["conversation_image_prompt"] = conversation_prompt
        reuse_existing_prompt = str(payload.get("use_existing_prompt") or "").lower() in {"1", "true", "yes", "on"}
        prompt = str(payload.get("prompt_text") or "").strip() if reuse_existing_prompt else ""
        if not prompt:
            prompt = str(conversation_prompt.get("prompt_ja") or "").strip()
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        prompt = prompt_support.apply_visual_style(prompt, context)
        prompt = prompt_support.forbid_text_in_image(prompt)
        safety_rewrite = text_support.rewrite_image_prompt_for_safety(
            self._text_ai_client,
            context,
            prompt,
            purpose=str(payload.get("image_type") or "live_scene"),
        )
        prompt = safety_rewrite.get("rewritten_prompt") or prompt
        prompt = prompt_support.forbid_text_in_image(prompt)
        visual_state = prompt_support.build_visual_state(context, state, prompt=prompt)
        state_json["visual_state"] = visual_state
        if safety_rewrite.get("changed"):
            state_json["image_prompt_safety_rewrite"] = safety_rewrite

        active_characters = image_support.resolve_active_characters(context, state_json, conversation_prompt)
        reference_paths, reference_asset_ids = self.collect_session_reference_assets(session_id, active_characters, limit=1)
        result = self._image_ai_client.generate_image(
            prompt,
            size=payload.get("size") or "1536x1024",
            quality=payload.get("quality") or "low",
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("image generation response did not include image_base64")
        file_name, file_path, file_size = image_support.store_generated_image(
            storage_root=self._storage_root(),
            project_id=session.project_id,
            session_id=session.id,
            image_base64=image_base64,
        )
        asset = self._asset_service.create_asset(
            session.project_id,
            {
                "asset_type": "generated_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "live_chat",
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_asset_ids,
                    }
                ),
            },
        )
        session_image = self._session_image_service.create_session_image(
            session_id,
            {
                "asset_id": asset.id,
                "image_type": payload.get("image_type") or "live_scene",
                "prompt_text": prompt,
                "state_json": state_json,
                "quality": payload.get("quality") or "low",
                "size": payload.get("size") or "1536x1024",
                "is_selected": 1,
                "is_reference": 1,
            },
        )
        self.select_image(session_image.id, update_observation=False)
        try:
            observation = self.analyze_displayed_image(
                file_path,
                prompt=result.get("revised_prompt") or prompt,
                source=payload.get("image_type") or "live_scene",
            )
            self._apply_observation_to_state(state_json, observation)
        except Exception:
            pass
        self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "visual_prompt_text": result.get("revised_prompt") or prompt,
            },
        )
        return self.serialize_session_image(session_image)

    def register_uploaded_image(self, session_id: int, asset_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        asset = self._asset_service.get_asset(asset_id)
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        if asset and getattr(asset, "file_path", None):
            try:
                observation = self.analyze_displayed_image(
                    asset.file_path,
                    prompt=payload.get("prompt_text"),
                    source="uploaded_live_scene",
                )
                self._apply_observation_to_state(state_json, observation)
            except Exception:
                pass
        session_image = self._session_image_service.create_session_image(
            session_id,
            {
                "asset_id": asset_id,
                "image_type": payload.get("image_type") or "live_scene",
                "prompt_text": payload.get("prompt_text"),
                "state_json": state_json if state_json else payload.get("state_json"),
                "quality": payload.get("quality") or "external",
                "size": payload.get("size") or "uploaded",
                "is_selected": 1 if payload.get("is_selected", True) else 0,
                "is_reference": 1 if payload.get("is_reference", False) else 0,
            },
        )
        if payload.get("is_selected", True):
            self.select_image(session_image.id, update_observation=False)
            if state_json:
                self._session_state_service.upsert_state(
                    session_id,
                    {
                        "state_json": state_json,
                        "visual_prompt_text": payload.get("prompt_text"),
                    },
                )
        return self.serialize_session_image(session_image)

    def list_costumes(self, session_id: int):
        self.ensure_initial_costume(session_id)
        local_rows = self._session_image_service.list_costumes(session_id)
        selected_local = next((item for item in local_rows if item.is_selected), None)
        library_rows = self._session_image_service.list_costume_library(session_id)
        selected_asset_id = selected_local.asset_id if selected_local else None
        seen_asset_ids = set()
        serialized = []
        for item in library_rows:
            if item.asset_id in seen_asset_ids:
                continue
            seen_asset_ids.add(item.asset_id)
            data = self.serialize_session_image(item)
            if item.session_id != session_id:
                data["is_shared"] = True
                data["is_selected"] = bool(selected_asset_id and item.asset_id == selected_asset_id)
            else:
                data["is_shared"] = bool(getattr(item, "linked_from_image_id", None))
            serialized.append(data)
        return serialized

    def select_costume(self, session_id: int, session_image_id: int):
        row = self._session_image_service.get_session_image(session_image_id)
        if not row or row.image_type not in {"costume_initial", "costume_reference"}:
            return None
        if row.session_id != session_id:
            keys = self._resolve_costume_library_keys(session_id)
            if (
                row.image_type != "costume_reference"
                or row.owner_user_id != keys.get("owner_user_id")
                or row.character_id != keys.get("character_id")
            ):
                return None
            row = self._session_image_service.create_costume_link_for_session(session_id, row.id)
            if not row:
                return None
        selected = self._session_image_service.select_session_image(row.id)
        return self.serialize_session_image(selected)

    def register_uploaded_costume(self, session_id: int, asset_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        session_image = self._session_image_service.create_session_image(
            session_id,
            {
                "asset_id": asset_id,
                **self._resolve_costume_library_keys(session_id),
                "image_type": "costume_reference",
                "prompt_text": payload.get("prompt_text"),
                "state_json": {
                    "source": "costume_upload",
                    "note": payload.get("note") or "",
                },
                "quality": "uploaded",
                "size": "uploaded",
                "is_selected": 0,
            },
        )
        selected = self._session_image_service.select_session_image(session_image.id)
        return self.serialize_session_image(selected)

    def delete_costume(self, session_id: int, session_image_id: int):
        row = self._session_image_service.get_session_image(session_image_id)
        if not row or row.session_id != session_id or row.image_type != "costume_reference":
            return None
        result = self._session_image_service.delete_costume(session_id, session_image_id)
        if not result:
            return None
        selected = self._session_image_service.get_selected_costume(session_id)
        return {
            "session_id": session_id,
            "deleted_id": result.get("deleted_id"),
            "selected_costume": self.serialize_session_image(selected),
            "costumes": self.list_costumes(session_id),
        }

    def _resolve_target_character(self, context: dict, character_id: int | None = None):
        characters = context.get("characters") or []
        if character_id:
            for character in characters:
                if int(character.get("id") or 0) == int(character_id):
                    return character
        return characters[0] if characters else None

    def _build_costume_context_text(self, context: dict) -> str:
        state_json = (context.get("state") or {}).get("state_json") or {}
        displayed_image = state_json.get("displayed_image_observation") or {}
        scene_progression = state_json.get("scene_progression") or {}
        conversation_lines = []
        for message in (context.get("messages") or [])[-10:]:
            speaker = message.get("speaker_name") or message.get("sender_type") or ""
            text = str(message.get("message_text") or "").strip()
            if text:
                conversation_lines.append(f"{speaker}: {text[:220]}")
        parts = [
            f"現在の場所: {state_json.get('location') or scene_progression.get('location') or ''}",
            f"現在の背景: {state_json.get('background') or scene_progression.get('background') or ''}",
            f"現在の場面要約: {state_json.get('focus_summary') or scene_progression.get('focus_summary') or ''}",
            f"表示中画像の観測: {displayed_image.get('short_summary') or ''}",
            "直近の会話:",
            "\n".join(conversation_lines),
        ]
        return "\n".join(part for part in parts if str(part or "").strip())

    def generate_costume(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        instruction = str(payload.get("prompt_text") or "").strip()
        if not instruction:
            raise ValueError("prompt_text is required")
        context = self._context_provider(session_id)
        character = self._resolve_target_character(context, payload.get("character_id"))
        if not character:
            raise ValueError("target character is required")
        selected_costume = self._session_image_service.get_selected_costume(session_id)
        reference_paths = []
        reference_asset_ids = []
        if selected_costume:
            asset = self._asset_service.get_asset(selected_costume.asset_id)
            if asset and getattr(asset, "file_path", None):
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)
        if not reference_paths:
            base_asset = character.get("base_asset") or {}
            if base_asset.get("file_path"):
                reference_paths.append(base_asset["file_path"])
                reference_asset_ids.append(base_asset.get("id"))
        if not reference_paths:
            raise ValueError("costume reference image is required")
        art_style = character.get("art_style") or ""
        costume_context = self._build_costume_context_text(context)
        rewrite = text_support.rewrite_costume_instruction(
            self._text_ai_client,
            context,
            character,
            instruction,
            costume_context,
        )
        rewritten_instruction = rewrite.get("rewritten_instruction") or instruction
        safety_note = rewrite.get("safety_note") or ""
        negative_note = rewrite.get("negative_note") or ""
        prompt = (
            "同一キャラクターの衣装参照画像を生成してください。\n"
            "参照画像と同じ人物として、顔、髪型、体型、雰囲気、キャラクター性を保つ。\n"
            "変更するのは主に衣装と小物のみ。\n"
            f"画像生成向けに整理した衣装指示:\n{rewritten_instruction}\n"
            f"安全な表現方針:\n{safety_note}\n"
            f"避ける表現:\n{negative_note}\n"
            f"キャラクター名: {character.get('name') or ''}\n"
            f"画風・スタイル指定: {art_style}\n"
            f"会話と現在場面の文脈:\n{costume_context}\n"
            "衣装は直近の会話や現在場面に自然に合うものにする。"
            "ノベルゲームのキャラクター衣装差分として、華やかさ、かわいさ、大人っぽさ、適度な色気をファッション表現で出す。\n"
            "例えば海やビーチに行く流れなら、作業着ではなく、場面に合う魅力的なビーチファッションやリゾート服として解釈する。\n"
            "色気は衣装のシルエット、色、素材感、アクセサリー、表情、品のあるポーズで表現する。\n"
            "裸体、性的行為、局部や胸部の過度な強調、透け表現の強調、幼く見える表現は禁止。\n"
            "キャラクター単体、全身または膝上、シンプル背景、衣装が分かる構図。\n"
            "ライブチャット用の参照画像なので、複雑な背景やイベントCG構図にはしない。\n"
        )
        prompt = prompt_support.forbid_text_in_image(prompt)
        safety_rewrite = {
            "rewritten_prompt": prompt,
            "changed": False,
            "safety_reason": "costume prompt already passed through costume-specific AI rewrite",
        }
        result = self._image_ai_client.generate_image(
            prompt,
            size=payload.get("size") or "1024x1536",
            quality=payload.get("quality") or "medium",
            input_image_paths=reference_paths,
            input_fidelity="high",
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("costume image generation response did not include image_base64")
        file_name, file_path, file_size = image_support.store_generated_image(
            storage_root=self._storage_root(),
            project_id=session.project_id,
            session_id=session.id,
            image_base64=image_base64,
        )
        asset = self._asset_service.create_asset(
            session.project_id,
            {
                "asset_type": "costume_reference",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "costume_room",
                        "instruction": instruction,
                        "rewritten_instruction": rewritten_instruction,
                        "safety_note": safety_note,
                        "negative_note": negative_note,
                        "image_prompt_safety_rewrite": safety_rewrite,
                        "reference_asset_ids": reference_asset_ids,
                        "revised_prompt": result.get("revised_prompt"),
                    }
                ),
            },
        )
        row = self._session_image_service.create_session_image(
            session_id,
            {
                "asset_id": asset.id,
                **self._resolve_costume_library_keys(session_id, context),
                "image_type": "costume_reference",
                "prompt_text": prompt,
                "state_json": {
                    "source": "costume_room",
                    "instruction": instruction,
                    "rewritten_instruction": rewritten_instruction,
                    "safety_note": safety_note,
                    "negative_note": negative_note,
                    "image_prompt_safety_rewrite": safety_rewrite,
                    "character_id": character.get("id"),
                    "reference_asset_ids": reference_asset_ids,
                },
                "quality": payload.get("quality") or "medium",
                "size": payload.get("size") or "1024x1536",
                "is_selected": 1,
                "is_reference": 0,
            },
        )
        self._session_image_service.select_session_image(row.id)
        return self.serialize_session_image(row)

    def select_image(self, session_image_id: int, *, update_observation: bool = True):
        row = self._session_image_service.select_session_image(session_image_id)
        if not row:
            return None
        self._chat_session_service.update_session(row.session_id, {"active_image_id": row.asset_id})
        if not update_observation:
            return self.serialize_session_image(row)
        asset = self._asset_service.get_asset(row.asset_id)
        if asset and getattr(asset, "file_path", None):
            try:
                state_json = self._load_json(getattr(row, "state_json", None)) or {}
                observation = self.analyze_displayed_image(
                    asset.file_path,
                    prompt=row.prompt_text,
                    source=row.image_type or "selected_image",
                )
                self._apply_observation_to_state(state_json, observation)
                self._session_state_service.upsert_state(
                    row.session_id,
                    {
                        "state_json": state_json,
                        "visual_prompt_text": row.prompt_text,
                    },
                )
            except Exception:
                pass
        return self.serialize_session_image(row)

    def set_reference_image(self, session_id: int, session_image_id: int, is_reference: bool):
        row = self._session_image_service.set_reference(session_id, session_image_id, is_reference)
        if not row:
            return None
        return self.serialize_session_image(row)
