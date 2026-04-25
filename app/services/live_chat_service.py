from __future__ import annotations

import os

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..utils import json_util
from . import live_chat_image_support as image_support
from . import live_chat_prompt_support as prompt_support
from . import live_chat_text_support as text_support
from .asset_service import AssetService
from .character_service import CharacterService
from .chat_message_service import ChatMessageService
from .chat_session_service import ChatSessionService
from .project_service import ProjectService
from .session_gift_event_service import SessionGiftEventService
from .session_image_service import SessionImageService
from .session_state_service import SessionStateService
from .world_service import WorldService


class LiveChatService:
    def __init__(
        self,
        chat_session_service: ChatSessionService | None = None,
        chat_message_service: ChatMessageService | None = None,
        session_state_service: SessionStateService | None = None,
        session_image_service: SessionImageService | None = None,
        project_service: ProjectService | None = None,
        character_service: CharacterService | None = None,
        asset_service: AssetService | None = None,
        session_gift_event_service: SessionGiftEventService | None = None,
        world_service: WorldService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._chat_session_service = chat_session_service or ChatSessionService()
        self._chat_message_service = chat_message_service or ChatMessageService()
        self._session_state_service = session_state_service or SessionStateService()
        self._session_image_service = session_image_service or SessionImageService()
        self._project_service = project_service or ProjectService()
        self._character_service = character_service or CharacterService()
        self._asset_service = asset_service or AssetService()
        self._session_gift_event_service = session_gift_event_service or SessionGiftEventService()
        self._world_service = world_service or WorldService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()

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

    def _serialize_character(self, character):
        base_asset = self._asset_service.get_asset(character.base_asset_id) if getattr(character, "base_asset_id", None) else None
        memory_profile = self._load_json(getattr(character, "memory_profile_json", None)) or {}
        if not isinstance(memory_profile, dict):
            memory_profile = {}
        return {
            "id": character.id,
            "name": character.name,
            "role": character.role,
            "first_person": character.first_person,
            "second_person": character.second_person,
            "personality": character.personality,
            "speech_style": character.speech_style,
            "speech_sample": character.speech_sample,
            "ng_rules": character.ng_rules,
            "appearance_summary": character.appearance_summary,
            "memory_notes": getattr(character, "memory_notes", None),
            "favorite_items": self._load_json(getattr(character, "favorite_items_json", None)) or [],
            "memory_profile": memory_profile,
            "is_guide": bool(character.is_guide),
            "base_asset": self._serialize_asset(base_asset),
        }

    def _serialize_session(self, row):
        return {
            "id": row.id,
            "project_id": row.project_id,
            "owner_user_id": getattr(row, "owner_user_id", None),
            "title": row.title,
            "session_type": row.session_type,
            "status": row.status,
            "privacy_status": getattr(row, "privacy_status", "private"),
            "active_image_id": row.active_image_id,
            "player_name": row.player_name,
            "settings_json": self._load_json(row.settings_json),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def _serialize_message(self, row):
        return {
            "id": row.id,
            "session_id": row.session_id,
            "sender_type": row.sender_type,
            "speaker_name": row.speaker_name,
            "message_text": row.message_text,
            "order_no": row.order_no,
            "message_role": row.message_role,
            "state_snapshot_json": self._load_json(row.state_snapshot_json),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
        }

    def _serialize_state(self, row):
        if row is None:
            return {
                "state_json": {},
                "narration_note": None,
                "visual_prompt_text": None,
            }
        return {
            "id": row.id,
            "session_id": row.session_id,
            "state_json": self._load_json(row.state_json) or {},
            "narration_note": row.narration_note,
            "visual_prompt_text": row.visual_prompt_text,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def _serialize_session_image(self, row):
        asset = self._asset_service.get_asset(row.asset_id)
        return {
            "id": row.id,
            "session_id": row.session_id,
            "asset_id": row.asset_id,
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

    def _collect_session_reference_assets(self, session_id: int, active_characters: list[dict], *, limit: int = 1):
        session_images = self._session_image_service.list_session_images(session_id)
        reference_paths = []
        reference_asset_ids = []
        for row in session_images:
            if not bool(getattr(row, "is_reference", 0)):
                continue
            asset = self._asset_service.get_asset(row.asset_id)
            if not asset or not getattr(asset, "file_path", None):
                continue
            reference_paths.append(asset.file_path)
            reference_asset_ids.append(asset.id)
            if len(reference_paths) >= limit:
                break
        if reference_paths:
            return reference_paths, reference_asset_ids
        return image_support.collect_reference_assets(active_characters, limit=limit)

    def _serialize_gift_event(self, row):
        asset = self._asset_service.get_asset(row.asset_id) if getattr(row, "asset_id", None) else None
        return {
            "id": row.id,
            "session_id": row.session_id,
            "actor_type": row.actor_type,
            "character_id": row.character_id,
            "asset_id": row.asset_id,
            "gift_direction": row.gift_direction,
            "recognized_label": row.recognized_label,
            "recognized_tags": self._load_json(row.recognized_tags_json) or [],
            "reaction_summary": row.reaction_summary,
            "evaluation_delta": row.evaluation_delta,
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "asset": self._serialize_asset(asset),
        }

    def _selected_character_ids_from_session(self, session) -> list[int]:
        settings_json = self._load_json(getattr(session, "settings_json", None)) or {}
        if not isinstance(settings_json, dict):
            return []
        raw_value = settings_json.get("selected_character_ids")
        if raw_value is None and settings_json.get("selected_character_id") is not None:
            raw_value = [settings_json.get("selected_character_id")]
        if not isinstance(raw_value, list):
            return []
        normalized = []
        seen = set()
        for item in raw_value:
            try:
                character_id = int(item)
            except (TypeError, ValueError):
                continue
            if character_id <= 0 or character_id in seen:
                continue
            seen.add(character_id)
            normalized.append(character_id)
        return normalized

    def _select_characters(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return []
        all_characters = self._character_service.list_characters(session.project_id)
        selected_ids = set(self._selected_character_ids_from_session(session))
        scoped_characters = [
            character for character in all_characters
            if not selected_ids or character.id in selected_ids
        ]
        target_characters = scoped_characters or all_characters
        return [self._serialize_character(character) for character in target_characters]

    def _resolve_target_character(self, context: dict, character_id: int | None = None):
        characters = context.get("characters") or []
        if character_id:
            for character in characters:
                if int(character.get("id") or 0) == int(character_id):
                    return character
        return characters[0] if characters else None

    def _contains_memory_match(self, gift_text: str, memory_item: str) -> bool:
        gift_text = str(gift_text or "").strip().lower()
        memory_item = str(memory_item or "").strip().lower()
        if not gift_text or not memory_item:
            return False
        return memory_item in gift_text or gift_text in memory_item

    def _evaluate_gift_for_character(self, character: dict, recognized_label: str, recognized_tags: list[str] | None = None):
        profile = dict(character.get("memory_profile") or {})
        romance = dict(profile.get("romance_preferences") or {})
        gift_terms = [recognized_label, *(recognized_tags or []), *(character.get("favorite_items") or [])]
        normalized_gift_text = " ".join(str(item or "") for item in gift_terms if str(item or "").strip())
        score = 0
        reasons = []
        mood = "neutral"

        def apply_matches(items, delta, reason_label):
            nonlocal score
            for item in items or []:
                if self._contains_memory_match(normalized_gift_text, item):
                    score += delta
                    reasons.append(f"{reason_label}: {item}")

        apply_matches(profile.get("likes") or character.get("favorite_items") or [], 16, "likes")
        apply_matches(profile.get("hobbies") or [], 10, "hobby")
        apply_matches(profile.get("dislikes") or [], -14, "dislikes")
        apply_matches(profile.get("taboos") or [], -24, "taboo")
        apply_matches((romance.get("attraction_points") or []), 6, "romance")
        apply_matches((romance.get("boundaries") or []), -12, "boundary")

        if score >= 20:
            mood = "delighted"
        elif score >= 8:
            mood = "happy"
        elif score <= -18:
            mood = "upset"
        elif score <= -6:
            mood = "awkward"

        summary_map = {
            "delighted": f"{character.get('name') or 'Character'} is genuinely delighted by the gift.",
            "happy": f"{character.get('name') or 'Character'} reacts warmly to the gift.",
            "neutral": f"{character.get('name') or 'Character'} accepts the gift with calm curiosity.",
            "awkward": f"{character.get('name') or 'Character'} looks a little troubled by the gift choice.",
            "upset": f"{character.get('name') or 'Character'} is clearly unhappy with the gift.",
        }
        return {
            "score_delta": score,
            "mood": mood,
            "reasons": reasons,
            "summary": summary_map[mood],
        }

    def _build_gift_reply(self, context: dict, character: dict, recognized_label: str, evaluation: dict):
        player_name = context.get("session", {}).get("player_name") or "プレイヤー"
        mood = evaluation.get("mood")
        label = recognized_label or "その贈り物"
        lines = {
            "delighted": f"{player_name}、これ……{label}？ ちゃんと私の好みを覚えてくれてたんだ。すごく嬉しい。",
            "happy": f"{label}を選んでくれたんだね。ありがとう、こういう気持ちはちゃんと伝わるよ。",
            "neutral": f"{label}をくれるんだ。ふふ、どんな気持ちで選んでくれたのか、少し気になるな。",
            "awkward": f"{label}……気持ちは嬉しいけれど、ちょっとだけ困っちゃったかも。",
            "upset": f"{label}は、少し反応に困るかな……。でも、どうしてそれを選んだのかは聞かせてほしい。",
        }
        return {
            "speaker_name": character.get("name") or "キャラクター",
            "message_text": lines.get(mood) or lines["neutral"],
        }

    def _update_gift_state_memory(self, session_id: int, character: dict, recognized_label: str, recognized_tags: list[str], evaluation: dict):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        gift_memory = state_json.get("gift_memory") or {}
        if not isinstance(gift_memory, dict):
            gift_memory = {}
        history = gift_memory.get("history") or []
        if not isinstance(history, list):
            history = []
        history.append(
            {
                "character_name": character.get("name"),
                "recognized_label": recognized_label,
                "recognized_tags": recognized_tags,
                "evaluation_delta": evaluation.get("score_delta", 0),
                "reaction_summary": evaluation.get("summary"),
            }
        )
        gift_memory["history"] = history[-20:]
        gift_memory["last_gift"] = history[-1]
        state_json["gift_memory"] = gift_memory

        relationship_state = state_json.get("relationship_state") or {}
        if not isinstance(relationship_state, dict):
            relationship_state = {}
        character_state = relationship_state.get(character.get("name")) or {}
        if not isinstance(character_state, dict):
            character_state = {}
        character_state["gift_affection"] = int(character_state.get("gift_affection") or 0) + int(evaluation.get("score_delta") or 0)
        relationship_state[character.get("name")] = character_state
        state_json["relationship_state"] = relationship_state
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _append_character_memorable_event(self, character_id: int, character: dict, recognized_label: str, evaluation: dict):
        profile = dict(character.get("memory_profile") or {})
        events = list(profile.get("memorable_events") or [])
        event_text = f"Player gifted {recognized_label} ({evaluation.get('mood')})"
        lowered = {str(item or "").strip().lower() for item in events}
        if event_text.lower() not in lowered:
            events.append(event_text)
        profile["memorable_events"] = events[-20:]
        self._character_service.update_character(character_id, {"memory_profile": profile})

    def _fallback_gift_visual_direction(self, character: dict, recognized_label: str, recognized_tags: list[str], evaluation: dict) -> dict:
        combined = " ".join([recognized_label, *(recognized_tags or [])]).lower()
        show = evaluation.get("score_delta", 0) >= 6
        visual_direction = f"{character.get('name') or 'キャラクター'}が贈り物を受け取って反応している"
        expression = "やわらかく微笑んでいる"
        pose = "プレゼントを両手で大切に持っている"
        mood = evaluation.get("mood") or "neutral"

        if any(keyword in combined for keyword in ("服", "ワンピース", "制服", "ドレス", "ジャケット", "coat", "dress")):
            show = evaluation.get("score_delta", 0) >= 0
            visual_direction = f"{character.get('name') or 'キャラクター'}が贈られた服を気に入って、その場で試着して見せている"
            pose = "新しい服を着て、少し照れながら見せている"
            expression = "少し照れつつ嬉しそう"
        elif any(keyword in combined for keyword in ("ぬいぐるみ", "テディベア", "人形", "stuffed", "plush")):
            show = evaluation.get("score_delta", 0) >= 0
            visual_direction = f"{character.get('name') or 'キャラクター'}が贈られたぬいぐるみを抱きしめている"
            pose = "ぬいぐるみを胸元で抱きしめている"
            expression = "素直に嬉しそうで愛おしそう"
        elif any(keyword in combined for keyword in ("アクセサリ", "ネックレス", "イヤリング", "指輪", "リング", "bracelet")):
            show = evaluation.get("score_delta", 0) >= 0
            visual_direction = f"{character.get('name') or 'キャラクター'}が贈られたアクセサリを身につけて見せている"
            pose = "身につけたアクセサリにそっと触れて見せている"
            expression = "少し誇らしげで嬉しそう"
        elif any(keyword in combined for keyword in ("花", "花束", "ブーケ", "bouquet", "rose")):
            show = evaluation.get("score_delta", 0) >= 0
            visual_direction = f"{character.get('name') or 'キャラクター'}が贈られた花束を抱えている"
            pose = "花束を抱え、香りを楽しむようにしている"
            expression = "華やかで嬉しそう"

        return {
            "show_gift_visual": bool(show),
            "visual_priority": "high" if show else "low",
            "reason": "gift heuristic fallback",
            "visual_direction": visual_direction,
            "expression": expression,
            "pose": pose,
            "mood": mood,
        }

    def _decide_gift_visual_direction(self, context: dict, character: dict, recognized_label: str, recognized_tags: list[str], evaluation: dict) -> dict:
        prompt_lines = [
            "Return only JSON.",
            "You are deciding whether a live chat visual should change after a gift event.",
            "Required keys: show_gift_visual, visual_priority, reason, visual_direction, expression, pose, mood.",
            "show_gift_visual must be true or false.",
            "Only set show_gift_visual true if the gift would create a visually meaningful scene right now.",
            "If the gift is clothing, accessory, plush toy, bouquet, or something the character would immediately use, prefer true.",
            "If the gift is a book, snack, small item, or something not visually dramatic right now, prefer false unless the reaction is very strong.",
            f"Character: {character.get('name') or 'character'}",
            f"Role: {character.get('role') or ''}",
            f"Personality: {character.get('personality') or ''}",
            f"Gift label: {recognized_label}",
            f"Gift tags: {', '.join(recognized_tags or [])}",
            f"Reaction summary: {evaluation.get('summary') or ''}",
            f"Score delta: {evaluation.get('score_delta', 0)}",
            "Recent conversation:",
        ]
        for item in (context.get("messages") or [])[-6:]:
            speaker = item.get("speaker_name") or item.get("sender_type") or "speaker"
            text = str(item.get("message_text") or "").strip()
            if text:
                prompt_lines.append(f"- {speaker}: {text[:140]}")
        try:
            result = self._text_ai_client.extract_state_json("\n".join(prompt_lines))
            parsed = result.get("parsed_json") or {}
            if not isinstance(parsed, dict):
                raise RuntimeError("gift visual decision is invalid")
            parsed["show_gift_visual"] = bool(parsed.get("show_gift_visual"))
            parsed["visual_priority"] = str(parsed.get("visual_priority") or "low").strip() or "low"
            parsed["reason"] = str(parsed.get("reason") or "").strip()
            parsed["visual_direction"] = str(parsed.get("visual_direction") or "").strip()
            parsed["expression"] = str(parsed.get("expression") or "").strip()
            parsed["pose"] = str(parsed.get("pose") or "").strip()
            parsed["mood"] = str(parsed.get("mood") or evaluation.get("mood") or "").strip()
            if not parsed["visual_direction"]:
                raise RuntimeError("gift visual direction is empty")
            return parsed
        except Exception:
            return self._fallback_gift_visual_direction(character, recognized_label, recognized_tags, evaluation)

    def _build_gift_visual_prompt(self, context: dict, character: dict, recognized_label: str, visual_decision: dict) -> str:
        world_name = context.get("world", {}).get("name") or ""
        world_overview = context.get("world", {}).get("overview") or ""
        location = ((context.get("state") or {}).get("state_json") or {}).get("location") or ""
        prompt_parts = [
            "visual novel event CG, first-person POV, viewer is the player, do not show the player character, no text, no subtitles, no speech bubbles, no watermark",
            f"main subject: {character.get('name') or 'character'}",
            f"scene: {visual_decision.get('visual_direction') or ''}",
            f"expression: {visual_decision.get('expression') or ''}",
            f"pose: {visual_decision.get('pose') or ''}",
            f"gift item: {recognized_label}",
            f"mood: {visual_decision.get('mood') or ''}",
        ]
        if location:
            prompt_parts.append(f"location: {location}")
        if world_name:
            prompt_parts.append(f"world: {world_name}")
        if world_overview:
            prompt_parts.append(f"world details: {world_overview[:180]}")
        appearance = character.get("appearance_summary") or ""
        if appearance:
            prompt_parts.append(f"character appearance: {appearance[:280]}")
        prompt_parts.append("show the character naturally using or holding the gift if appropriate")
        return prompt_support.normalize_first_person_visual_prompt(", ".join(part for part in prompt_parts if part))

    def _generate_gift_visual_image(self, session, context: dict, character: dict, recognized_label: str, recognized_tags: list[str], visual_decision: dict):
        if not visual_decision.get("show_gift_visual"):
            return None
        prompt = self._build_gift_visual_prompt(context, character, recognized_label, visual_decision)
        reference_paths, reference_asset_ids = self._collect_session_reference_assets(session.id, [character], limit=1)
        result = self._image_ai_client.generate_image(
            prompt,
            size="1536x1024",
            quality="low",
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("gift image generation response did not include image_base64")
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        file_name, file_path, file_size = image_support.store_generated_image(
            storage_root=storage_root,
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
                        "source": "gift_visual",
                        "recognized_label": recognized_label,
                        "reference_asset_ids": reference_asset_ids,
                        "revised_prompt": result.get("revised_prompt"),
                    }
                ),
            },
        )
        state_json = dict((context.get("state") or {}).get("state_json") or {})
        state_json["gift_visual_context"] = {
            "recognized_label": recognized_label,
            "recognized_tags": recognized_tags,
            "visual_direction": visual_decision.get("visual_direction"),
            "expression": visual_decision.get("expression"),
            "pose": visual_decision.get("pose"),
            "mood": visual_decision.get("mood"),
        }
        if visual_decision.get("visual_direction"):
            state_json["focus_summary"] = visual_decision["visual_direction"]
        if visual_decision.get("mood"):
            state_json["mood"] = visual_decision["mood"]
        session_image = self._session_image_service.create_session_image(
            session.id,
            {
                "asset_id": asset.id,
                "image_type": "gift_reaction",
                "prompt_text": prompt,
                "state_json": state_json,
                "quality": "low",
                "size": "1536x1024",
                "is_selected": 1,
                "is_reference": 1,
            },
        )
        self.select_image(session_image.id)
        self._session_state_service.upsert_state(
            session.id,
            {
                "state_json": state_json,
                "visual_prompt_text": result.get("revised_prompt") or prompt,
                "narration_note": visual_decision.get("visual_direction"),
            },
        )
        return self._serialize_session_image(session_image)

    def list_sessions(
        self,
        project_id: int,
        owner_user_id: int | None = None,
        include_private_details: bool = True,
        detail_owner_user_id: int | None = None,
    ):
        items = self._chat_session_service.list_sessions(project_id, owner_user_id=owner_user_id)
        serialized = []
        for item in items:
            can_include_details = include_private_details or (
                detail_owner_user_id is not None and getattr(item, "owner_user_id", None) == detail_owner_user_id
            )
            messages = self._chat_message_service.list_messages(item.id)
            images = self._session_image_service.list_session_images(item.id)
            selected_image_row = next((image for image in images if image.is_selected), None)
            session_characters = self._select_characters(item.id)
            serialized.append(
                {
                    **self._serialize_session(item),
                    "message_count": len(messages),
                    "last_message_text": messages[-1].message_text if messages and can_include_details else None,
                    "characters": session_characters,
                    "selected_image": (
                        self._serialize_session_image(selected_image_row)
                        if selected_image_row and can_include_details
                        else None
                    ),
                }
            )
        return serialized

    def create_session(self, project_id: int, payload: dict | None = None, owner_user_id: int | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.create_session(project_id, payload, owner_user_id=owner_user_id)
        if not session:
            return None
        initial_state = {}
        selected_character_ids = self._selected_character_ids_from_session(session)
        if selected_character_ids:
            initial_state["active_character_ids"] = selected_character_ids
        self._session_state_service.upsert_state(session.id, {"state_json": initial_state})
        return self.get_session_context(session.id)

    def _preserve_locked_session_characters(self, session_id: int, payload: dict) -> dict:
        if "settings_json" not in payload:
            return payload
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return payload
        locked_character_ids = self._selected_character_ids_from_session(session)
        settings_json = self._load_json(payload.get("settings_json")) or {}
        if not isinstance(settings_json, dict):
            settings_json = {}
        settings_json.pop("selected_character_id", None)
        if locked_character_ids:
            settings_json["selected_character_ids"] = locked_character_ids
        else:
            settings_json.pop("selected_character_ids", None)
        payload["settings_json"] = settings_json
        return payload

    def update_session(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        payload = self._preserve_locked_session_characters(session_id, payload)
        session = self._chat_session_service.update_session(session_id, payload)
        if not session:
            return None
        selected_character_ids = self._selected_character_ids_from_session(session)
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        if selected_character_ids:
            state_json["active_character_ids"] = selected_character_ids
        else:
            state_json.pop("active_character_ids", None)
        self._session_state_service.upsert_state(session_id, {"state_json": state_json})
        return self.get_session_context(session_id)

    def delete_message(self, session_id: int, message_id: int):
        row = self._chat_message_service.delete_message(message_id)
        if not row or row.session_id != session_id:
            return None
        context = self.get_session_context(session_id)
        self._update_conversation_evaluation(session_id, context)
        return self.get_session_context(session_id)

    def get_session_context(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        project = self._project_service.get_project(session.project_id)
        state = self._session_state_service.get_state(session_id)
        messages = self._chat_message_service.list_messages(session_id)
        images = self._session_image_service.list_session_images(session_id)
        gift_events = self._session_gift_event_service.list_gift_events(session_id)
        selected_image = next((item for item in images if item.is_selected), None)
        characters = self._select_characters(session_id)
        world = self._world_service.get_world(session.project_id)
        if not messages and characters:
            opening_context = {
                "project": {
                    "id": project.id if project else session.project_id,
                    "title": project.title if project else None,
                    "genre": project.genre if project else None,
                },
                "story_outline": {},
                "world": {
                    "name": getattr(world, "name", None) if world else None,
                    "overview": getattr(world, "overview", None) if world else None,
                    "tone": getattr(world, "tone", None) if world else None,
                },
                "session": self._serialize_session(session),
                "messages": [],
                "state": self._serialize_state(state),
                "characters": characters,
            }
            self._create_opening_message(session, opening_context)
            messages = self._chat_message_service.list_messages(session_id)
        return {
            "project": {
                "id": project.id if project else session.project_id,
                "title": project.title if project else None,
                "genre": project.genre if project else None,
            },
            "story_outline": {},
            "world": {
                "name": getattr(world, "name", None) if world else None,
                "overview": getattr(world, "overview", None) if world else None,
                "tone": getattr(world, "tone", None) if world else None,
            },
            "session": self._serialize_session(session),
            "messages": [self._serialize_message(item) for item in messages],
            "state": self._serialize_state(state),
            "characters": characters,
            "images": [self._serialize_session_image(item) for item in images],
            "gift_events": [self._serialize_gift_event(item) for item in gift_events],
            "selected_image": self._serialize_session_image(selected_image) if selected_image else None,
        }

    def _create_opening_message(self, session, context: dict):
        opening = text_support.generate_opening_message(self._text_ai_client, context)
        self._chat_message_service.create_message(
            session.id,
            {
                "sender_type": "character",
                "speaker_name": opening["speaker_name"],
                "message_text": opening["message_text"],
                "message_role": "assistant",
            },
        )

    def _update_line_visual_note(self, session_id: int, context: dict):
        latest_character_message = None
        for message in reversed(context["messages"]):
            if message.get("sender_type") == "character":
                latest_character_message = message
                break
        if not latest_character_message:
            return None
        note = text_support.generate_line_visual_note(
            self._text_ai_client,
            context,
            latest_character_message.get("speaker_name") or "character",
            latest_character_message.get("message_text") or "",
        )
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json["line_visual_note"] = note
        if note.get("location"):
            state_json["location"] = note["location"]
        if note.get("background"):
            state_json["background"] = note["background"]
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _sync_character_memory_from_session(self, context: dict, session_memory: dict | None):
        session_memory = dict(session_memory or {})
        memory_map = session_memory.get("character_memories") or {}
        if not isinstance(memory_map, dict):
            return
        for character in context.get("characters") or []:
            character_memory = memory_map.get(character.get("name")) or {}
            if not isinstance(character_memory, dict):
                continue
            current_profile = dict(character.get("memory_profile") or {})
            current_romance = dict(current_profile.get("romance_preferences") or {})
            merged_profile = {
                "likes": [],
                "dislikes": [],
                "hobbies": [],
                "taboos": [],
                "memorable_events": [],
                "romance_preferences": {
                    "favorite_approach": [],
                    "avoid_approach": [],
                    "attraction_points": [],
                    "boundaries": [],
                },
            }

            def merge_values(*sources):
                merged = []
                seen = set()
                for source in sources:
                    for item in source or []:
                        text = str(item or "").strip()
                        if not text:
                            continue
                        lowered = text.lower()
                        if lowered in seen:
                            continue
                        seen.add(lowered)
                        merged.append(text[:160])
                return merged

            merged_profile["likes"] = merge_values(
                current_profile.get("likes") or character.get("favorite_items") or [],
                character_memory.get("likes") or character_memory.get("favorite_items") or [],
            )
            merged_profile["dislikes"] = merge_values(current_profile.get("dislikes") or [], character_memory.get("dislikes") or [])
            merged_profile["hobbies"] = merge_values(current_profile.get("hobbies") or [], character_memory.get("hobbies") or [])
            merged_profile["taboos"] = merge_values(current_profile.get("taboos") or [], character_memory.get("taboos") or [])
            merged_profile["memorable_events"] = merge_values(
                current_profile.get("memorable_events") or [],
                character_memory.get("memorable_events") or [],
            )
            merged_profile["romance_preferences"] = {
                "favorite_approach": merge_values(
                    current_romance.get("favorite_approach") or [],
                    (character_memory.get("romance_preferences") or {}).get("favorite_approach") or [],
                ),
                "avoid_approach": merge_values(
                    current_romance.get("avoid_approach") or [],
                    (character_memory.get("romance_preferences") or {}).get("avoid_approach") or [],
                ),
                "attraction_points": merge_values(
                    current_romance.get("attraction_points") or [],
                    (character_memory.get("romance_preferences") or {}).get("attraction_points") or [],
                ),
                "boundaries": merge_values(
                    current_romance.get("boundaries") or [],
                    (character_memory.get("romance_preferences") or {}).get("boundaries") or [],
                ),
            }
            existing_note = str(character.get("memory_notes") or "").strip()
            note_parts = [part for part in [existing_note, *list(character_memory.get("notes") or [])] if str(part or "").strip()]
            merged_note = " / ".join(dict.fromkeys(str(part).strip()[:160] for part in note_parts if str(part).strip()))
            payload = {}
            if merged_profile != current_profile:
                payload["memory_profile"] = merged_profile
                payload["favorite_items"] = merged_profile["likes"]
            if merged_note and merged_note != existing_note:
                payload["memory_notes"] = merged_note
            if payload:
                self._character_service.update_character(character["id"], payload)

    def _update_session_memory(self, session_id: int, context: dict):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        session_memory = prompt_support.build_session_memory(context["messages"], state_json)
        state_json["session_memory"] = session_memory
        self._sync_character_memory_from_session(context, session_memory)
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _update_conversation_evaluation(self, session_id: int, context: dict):
        evaluation = text_support.generate_conversation_evaluation(self._text_ai_client, context)
        if evaluation is None:
            return None
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json["conversation_evaluation"] = evaluation
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _update_conversation_director(self, session_id: int, context: dict, user_message_text: str):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        director = text_support.generate_conversation_director(self._text_ai_client, context, user_message_text)
        relationship_state = dict(state_json.get("relationship_state") or {})
        relationship_state = prompt_support.apply_director_relationship_update(relationship_state, context, director)
        state_json["conversation_director"] = director
        state_json["relationship_state"] = relationship_state
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _update_scene_progression(self, session_id: int, context: dict, user_message_text: str):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        progression = text_support.generate_scene_progression(self._text_ai_client, context, user_message_text)
        state_json["scene_progression"] = progression
        if progression.get("location"):
            state_json["location"] = progression["location"]
        if progression.get("background"):
            state_json["background"] = progression["background"]
        if progression.get("focus_summary"):
            state_json["focus_summary"] = progression["focus_summary"]
        return self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "narration_note": progression.get("focus_summary"),
            },
        )

    def post_message(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        message_text = str(payload.get("message_text") or "").strip() or "話を進めて"
        user_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": payload.get("sender_type") or "user",
                "speaker_name": payload.get("speaker_name") or session.player_name or "プレイヤー",
                "message_text": message_text,
                "message_role": "player",
            },
        )
        created = [self._serialize_message(user_message)]
        context = self.get_session_context(session_id)
        self._update_scene_progression(session_id, context, user_message.message_text)
        context = self.get_session_context(session_id)
        self._update_conversation_director(session_id, context, user_message.message_text)
        context = self.get_session_context(session_id)
        auto_reply = str(payload.get("auto_reply", "true")).lower() not in {"0", "false", "no", "off"}
        if auto_reply:
            reply = text_support.generate_reply(self._text_ai_client, context, user_message.message_text)
            assistant_message = self._chat_message_service.create_message(
                session_id,
                {
                    "sender_type": "character",
                    "speaker_name": reply["speaker_name"],
                    "message_text": reply["message_text"],
                    "message_role": "assistant",
                },
            )
            created.append(self._serialize_message(assistant_message))
        updated_context = self.get_session_context(session_id)
        self._update_line_visual_note(session_id, updated_context)
        updated_context = self.get_session_context(session_id)
        self._update_session_memory(session_id, updated_context)
        updated_context = self.get_session_context(session_id)
        self._update_conversation_evaluation(session_id, updated_context)
        updated_context = self.get_session_context(session_id)
        state = self._session_state_service.extract_state(
            session=session,
            messages=updated_context["messages"],
            characters=updated_context["characters"],
        )
        return {
            "messages": created,
            "state": self._serialize_state(state),
            "session": updated_context["session"],
        }

    def extract_state(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        context = self.get_session_context(session_id)
        state = self._session_state_service.extract_state(
            session=session,
            messages=context["messages"],
            characters=context["characters"],
        )
        return self._serialize_state(state)

    def generate_image(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        context = self.get_session_context(session_id)
        state = context["state"]
        state_json = dict(state.get("state_json") or {})
        conversation_prompt = image_support.generate_japanese_conversation_image_prompt(self._text_ai_client, context, state)
        state_json["conversation_image_prompt"] = conversation_prompt
        reuse_existing_prompt = str(payload.get("use_existing_prompt") or "").lower() in {"1", "true", "yes", "on"}
        prompt = str(payload.get("prompt_text") or "").strip() if reuse_existing_prompt else ""
        if not prompt:
            prompt = str(conversation_prompt.get("prompt_ja") or "").strip()
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        visual_state = prompt_support.build_visual_state(context, state, prompt=prompt)
        state_json["visual_state"] = visual_state

        active_characters = image_support.resolve_active_characters(context, state_json, conversation_prompt)
        reference_paths, reference_asset_ids = self._collect_session_reference_assets(session_id, active_characters, limit=1)
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
        try:
            storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        except RuntimeError:
            storage_root = os.path.join(os.getcwd(), "storage")
        file_name, file_path, file_size = image_support.store_generated_image(
            storage_root=storage_root,
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
                "state_json": state.get("state_json") or {},
                "quality": payload.get("quality") or "low",
                "size": payload.get("size") or "1536x1024",
                "is_selected": 1,
                "is_reference": 1,
            },
        )
        self.select_image(session_image.id)
        self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "visual_prompt_text": result.get("revised_prompt") or prompt,
            },
        )
        return self._serialize_session_image(session_image)

    def register_uploaded_image(self, session_id: int, asset_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session_image = self._session_image_service.create_session_image(
            session_id,
            {
                "asset_id": asset_id,
                "image_type": payload.get("image_type") or "live_scene",
                "prompt_text": payload.get("prompt_text"),
                "state_json": payload.get("state_json"),
                "quality": payload.get("quality") or "external",
                "size": payload.get("size") or "uploaded",
                "is_selected": 1 if payload.get("is_selected", True) else 0,
                "is_reference": 1 if payload.get("is_reference", False) else 0,
            },
        )
        if payload.get("is_selected", True):
            self.select_image(session_image.id)
        return self._serialize_session_image(session_image)

    def select_image(self, session_image_id: int):
        row = self._session_image_service.select_session_image(session_image_id)
        if not row:
            return None
        self._chat_session_service.update_session(row.session_id, {"active_image_id": row.asset_id})
        return self._serialize_session_image(row)

    def set_reference_image(self, session_id: int, session_image_id: int, is_reference: bool):
        row = self._session_image_service.set_reference(session_id, session_image_id, is_reference)
        if not row:
            return None
        return self._serialize_session_image(row)

    def upload_gift(self, session_id: int, asset_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        asset = self._asset_service.get_asset(asset_id)
        if not asset:
            return None
        context = self.get_session_context(session_id)
        character = self._resolve_target_character(context, payload.get("character_id"))
        if not character:
            raise ValueError("target character is required")

        analysis_prompt = (
            "Return only JSON. Identify what gift is shown in this image for a romance live chat. "
            'Required keys: label, short_description, tags, likely_categories. '
            "label must be a short noun phrase in Japanese. tags and likely_categories must be arrays."
        )
        analysis = self._text_ai_client.analyze_image(asset.file_path, prompt=analysis_prompt)
        parsed = analysis.get("parsed_json") or {}
        recognized_label = str(parsed.get("label") or asset.file_name or "贈り物").strip()[:120]
        recognized_tags = [
            str(item or "").strip()[:80]
            for item in (parsed.get("tags") or [])
            if str(item or "").strip()
        ][:8]
        evaluation = self._evaluate_gift_for_character(character, recognized_label, recognized_tags)
        visual_decision = self._decide_gift_visual_direction(context, character, recognized_label, recognized_tags, evaluation)
        gift_event = self._session_gift_event_service.create_gift_event(
            session_id,
            {
                "actor_type": "player",
                "character_id": character.get("id"),
                "asset_id": asset_id,
                "gift_direction": "player_to_character",
                "recognized_label": recognized_label,
                "recognized_tags_json": recognized_tags,
                "reaction_summary": evaluation.get("summary"),
                "evaluation_delta": evaluation.get("score_delta", 0),
            },
        )
        gift_snapshot = {
            "gift": {
                "event_id": gift_event.id,
                "gift_direction": "player_to_character",
                "recognized_label": recognized_label,
                "recognized_tags": recognized_tags,
                "reaction_summary": evaluation.get("summary"),
                "evaluation_delta": evaluation.get("score_delta", 0),
                "asset": self._serialize_asset(asset),
            }
        }
        player_name = session.player_name or "プレイヤー"
        user_message_text = str(payload.get("message_text") or "").strip() or f"{recognized_label}を差し出した。"
        user_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "user",
                "speaker_name": player_name,
                "message_text": user_message_text,
                "message_role": "player",
                "state_snapshot_json": gift_snapshot,
            },
        )
        reply = self._build_gift_reply(context, character, recognized_label, evaluation)
        assistant_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": reply["speaker_name"],
                "message_text": reply["message_text"],
                "message_role": "assistant",
                "state_snapshot_json": gift_snapshot,
            },
        )
        self._update_gift_state_memory(session_id, character, recognized_label, recognized_tags, evaluation)
        self._append_character_memorable_event(character.get("id"), character, recognized_label, evaluation)
        generated_image = None
        try:
            generated_image = self._generate_gift_visual_image(
                session,
                context,
                character,
                recognized_label,
                recognized_tags,
                visual_decision,
            )
        except Exception:
            generated_image = None
        updated_context = self.get_session_context(session_id)
        self._update_session_memory(session_id, updated_context)
        updated_context = self.get_session_context(session_id)
        self._update_conversation_evaluation(session_id, updated_context)
        updated_context = self.get_session_context(session_id)
        return {
            "gift_event": self._serialize_gift_event(gift_event),
            "messages": [self._serialize_message(user_message), self._serialize_message(assistant_message)],
            "gift_visual_decision": visual_decision,
            "generated_image": generated_image,
            "session": updated_context["session"],
            "state": updated_context["state"],
        }
