from __future__ import annotations

import os
from typing import Callable

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..utils import json_util
from . import live_chat_image_support as image_support
from . import live_chat_prompt_support as prompt_support
from .asset_service import AssetService
from .chat_message_service import ChatMessageService
from .chat_session_service import ChatSessionService
from .letter_service import LetterService
from .live_chat_media_service import LiveChatMediaService
from .session_gift_event_service import SessionGiftEventService
from .session_image_service import SessionImageService
from .session_state_service import SessionStateService


class LiveChatGiftService:
    """Gift upload, recognition, reaction, and optional gift visual generation."""

    def __init__(
        self,
        *,
        chat_session_service: ChatSessionService,
        chat_message_service: ChatMessageService,
        session_state_service: SessionStateService,
        session_image_service: SessionImageService,
        asset_service: AssetService,
        session_gift_event_service: SessionGiftEventService,
        letter_service: LetterService,
        media_service: LiveChatMediaService,
        text_ai_client: TextAIClient,
        image_ai_client: ImageAIClient,
        context_provider: Callable[[int], dict],
        update_session_memory: Callable[[int, dict], object],
        update_conversation_evaluation: Callable[[int, dict], object],
        serialize_message: Callable[[object], dict],
    ):
        self._chat_session_service = chat_session_service
        self._chat_message_service = chat_message_service
        self._session_state_service = session_state_service
        self._session_image_service = session_image_service
        self._asset_service = asset_service
        self._session_gift_event_service = session_gift_event_service
        self._letter_service = letter_service
        self._media_service = media_service
        self._text_ai_client = text_ai_client
        self._image_ai_client = image_ai_client
        self._context_provider = context_provider
        self._update_session_memory = update_session_memory
        self._update_conversation_evaluation = update_conversation_evaluation
        self._serialize_message = serialize_message

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
            "mime_type": asset.mime_type,
            "file_size": asset.file_size,
            "file_path": asset.file_path,
            "url": self._build_media_url(asset.file_path),
            "metadata": self._load_json(asset.metadata_json) or {},
        }

    def serialize_gift_event(self, row):
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
            f"Nickname: {character.get('nickname') or ''}",
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
        reference_paths, reference_asset_ids = self._media_service.collect_session_reference_assets(session.id, [character], limit=1)
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
        try:
            observation = self._media_service.analyze_displayed_image(file_path, prompt=prompt, source="gift_visual")
            state_json["displayed_image_observation"] = observation
            if observation.get("location"):
                state_json["location"] = observation["location"]
            if observation.get("background"):
                state_json["background"] = observation["background"]
            if observation.get("short_summary"):
                state_json["focus_summary"] = observation["short_summary"]
        except Exception:
            observation = None
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
        self._media_service.select_image(session_image.id, update_observation=False)
        self._session_state_service.upsert_state(
            session.id,
            {
                "state_json": state_json,
                "visual_prompt_text": result.get("revised_prompt") or prompt,
                "narration_note": visual_decision.get("visual_direction"),
            },
        )
        return self._media_service.serialize_session_image(session_image)

    def upload_gift(self, session_id: int, asset_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        asset = self._asset_service.get_asset(asset_id)
        if not asset:
            return None
        context = self._context_provider(session_id)
        character = self._resolve_target_character(context, payload.get("character_id"))
        if not character:
            raise ValueError("target character is required")

        analysis_prompt = (
            "Return only JSON. Identify what gift is shown in this image for a romance live chat. "
            "Required keys: label, short_description, tags, likely_categories. "
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
        updated_context = self._context_provider(session_id)
        self._update_session_memory(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self._update_conversation_evaluation(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        new_letter = self._letter_service.try_generate_for_context(
            session,
            updated_context,
            trigger_type="gift",
        )
        return {
            "gift_event": self.serialize_gift_event(gift_event),
            "messages": [self._serialize_message(user_message), self._serialize_message(assistant_message)],
            "gift_visual_decision": visual_decision,
            "generated_image": generated_image,
            "session": updated_context["session"],
            "state": updated_context["state"],
            "new_letter": new_letter,
        }
