from __future__ import annotations

import threading
from datetime import datetime
from types import SimpleNamespace

from flask import current_app

from ..extensions import db
from ..clients.text_ai_client import TextAIClient
from ..utils import json_util
from . import live_chat_prompt_support as prompt_support
from . import live_chat_text_support as text_support
from .chat_message_service import ChatMessageService
from .chat_session_service import ChatSessionService
from .letter_service import LetterService
from .live_chat_media_service import LiveChatMediaService
from .session_state_service import SessionStateService
from .user_setting_service import UserSettingService
from .character_user_memory_service import CharacterUserMemoryService
from .character_memory_note_service import CharacterMemoryNoteService
from .session_objective_note_service import SessionObjectiveNoteService
from ..repositories.world_location_repository import WorldLocationRepository


class LiveChatConversationService:
    """Conversation-side state updates and scene-choice helpers."""

    def __init__(
        self,
        *,
        chat_session_service: ChatSessionService | None = None,
        chat_message_service: ChatMessageService | None = None,
        session_state_service: SessionStateService,
        letter_service: LetterService | None = None,
        media_service: LiveChatMediaService | None = None,
        text_ai_client: TextAIClient,
        context_provider=None,
        serialize_message=None,
        serialize_state=None,
        character_user_memory_service: CharacterUserMemoryService | None = None,
        character_memory_note_service: CharacterMemoryNoteService | None = None,
        session_objective_note_service: SessionObjectiveNoteService | None = None,
        world_location_repository: WorldLocationRepository | None = None,
    ):
        self._chat_session_service = chat_session_service
        self._chat_message_service = chat_message_service
        self._session_state_service = session_state_service
        self._letter_service = letter_service
        self._media_service = media_service
        self._text_ai_client = text_ai_client
        self._context_provider = context_provider
        self._serialize_message = serialize_message
        self._serialize_state = serialize_state
        self._character_user_memory_service = character_user_memory_service or CharacterUserMemoryService()
        self._character_memory_note_service = character_memory_note_service or CharacterMemoryNoteService()
        self._session_objective_note_service = session_objective_note_service or SessionObjectiveNoteService()
        self._world_location_repository = world_location_repository or WorldLocationRepository()

    def _update_character_user_memory(self, session, context: dict):
        if not session:
            return
        messages = context.get("messages") or []
        last_user = next((item for item in reversed(messages) if item.get("sender_type") == "user"), None)
        last_character = next((item for item in reversed(messages) if item.get("sender_type") == "character"), None)
        user_text = str((last_user or {}).get("message_text") or "").strip()
        character_text = str((last_character or {}).get("message_text") or "").strip()
        if not user_text and not character_text:
            return
        for character in context.get("characters") or []:
            character_id = int(character.get("id") or 0)
            if not character_id:
                continue
            summary = f"{character.get('name') or 'character'}との会話を継続中。"
            notes = " / ".join(item for item in [user_text[:200], character_text[:200]] if item)
            self._character_user_memory_service.update_from_event(
                user_id=int(session.owner_user_id),
                character_id=character_id,
                relationship_summary=summary,
                memory_notes=notes,
            )

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

    def update_line_visual_note(self, session_id: int, context: dict):
        latest = None
        for message in reversed(context.get("messages") or []):
            if message.get("sender_type") == "character":
                latest = message
                break
        if not latest:
            return None
        note = text_support.generate_line_visual_note(
            self._text_ai_client,
            context,
            latest.get("speaker_name") or "character",
            latest.get("message_text") or "",
        )
        if note is None:
            return None
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json["line_visual_note"] = note
        if note.get("location"):
            state_json["location"] = note["location"]
        if note.get("background"):
            state_json["background"] = note["background"]
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def update_session_memory(self, session_id: int, context: dict):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        session_memory = prompt_support.build_session_memory(context["messages"], state_json)
        state_json["session_memory"] = session_memory
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def update_conversation_evaluation(self, session_id: int, context: dict):
        evaluation = text_support.generate_conversation_evaluation(self._text_ai_client, context)
        if evaluation is None:
            return None
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json["conversation_evaluation"] = evaluation
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def update_conversation_director(self, session_id: int, context: dict, user_message_text: str):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        director = text_support.generate_conversation_director(self._text_ai_client, context, user_message_text)
        relationship_state = dict(state_json.get("relationship_state") or {})
        relationship_state = prompt_support.apply_director_relationship_update(relationship_state, context, director)
        state_json["conversation_director"] = director
        state_json["relationship_state"] = relationship_state
        updated = self._session_state_service.upsert_state(session_id, {"state_json": state_json})
        updated_context = self._context_provider(session_id) if self._context_provider else context
        self._session_objective_note_service.update_from_direction(
            self._text_ai_client,
            updated_context,
            source_ref=f"chat_session:{session_id}",
        )
        return updated

    def update_scene_progression(self, session_id: int, context: dict, user_message_text: str):
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

    def update_scene_choices(self, session_id: int, context: dict, assistant_message):
        if not assistant_message:
            return None
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        choices_result = text_support.generate_scene_choices(
            self._text_ai_client,
            context,
            assistant_message.speaker_name,
            assistant_message.message_text,
        )
        if choices_result.get("should_show_choices") and choices_result.get("choices"):
            state_json["scene_choices"] = {
                "source_message_id": assistant_message.id,
                "created_at": datetime.utcnow().isoformat(),
                "choices": choices_result["choices"][:3],
            }
        else:
            state_json.pop("scene_choices", None)
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def clear_scene_choices(self, session_id: int):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json.pop("scene_choices", None)
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def build_choice_image_prompt(self, context: dict, choice: dict) -> str:
        state_json = (context.get("state") or {}).get("state_json") or {}
        recent_lines = []
        for message in (context.get("messages") or [])[-6:]:
            speaker = message.get("speaker_name") or message.get("sender_type") or ""
            text = message.get("message_text") or ""
            if text:
                recent_lines.append(f"{speaker}: {text}")
        character_names = "、".join(character.get("name") or "" for character in context.get("characters") or [])
        prompt = (
            f"ユーザーが選択肢「{choice.get('label') or ''}」を選んだ。\n"
            f"場面指示: {choice.get('scene_instruction') or choice.get('label') or ''}\n"
            f"画像ヒント: {choice.get('image_prompt_hint') or ''}\n"
            f"現在の場所: {state_json.get('location') or ''}\n"
            f"現在の背景: {state_json.get('background') or ''}\n"
            f"登場キャラクター: {character_names}\n"
            "直近の会話:\n"
            + "\n".join(recent_lines)
            + "\nプレイヤー1人称視点。プレイヤーは画像に描かない。"
            "キャラクターだけを魅力的に表示し、選択した場面に移動したことが一目で分かる背景にする。"
            "選択中の衣装画像と同じ顔、髪型、体型、衣装を維持する。"
            "ノベルゲームのイベントCGとしてドラマチックにする。"
        )
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        prompt = prompt_support.apply_visual_style(prompt, context)
        return prompt_support.forbid_text_in_image(prompt)

    def apply_directed_scene(self, session_id: int, context: dict, user_message_text: str, intent: dict):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        scene_update = text_support.generate_narration_scene(
            self._text_ai_client,
            context,
            user_message_text,
            intent,
        )
        state_json["input_intent"] = intent
        state_json["scene_progression"] = scene_update
        state_json["directed_scene"] = scene_update
        if scene_update.get("location"):
            state_json["location"] = scene_update["location"]
        if scene_update.get("background"):
            state_json["background"] = scene_update["background"]
        if scene_update.get("focus_summary"):
            state_json["focus_summary"] = scene_update["focus_summary"]
        return self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "narration_note": scene_update.get("focus_summary"),
                "visual_prompt_text": scene_update.get("image_focus") or scene_update.get("focus_summary"),
            },
        )

    def _state_json_from_context(self, context: dict | None) -> dict:
        state = (context or {}).get("state") or {}
        state_json = state.get("state_json") or {}
        return state_json if isinstance(state_json, dict) else {}

    def _scene_value_changed(self, before: dict, after: dict, key: str) -> bool:
        before_value = str(before.get(key) or "").strip()
        after_value = str(after.get(key) or "").strip()
        return bool(after_value and after_value != before_value)

    def _recent_character_transition_offer_exists(self, context: dict) -> bool:
        transition_keywords = (
            "行こう",
            "向かおう",
            "連れて",
            "見せて",
            "見に行",
            "歩こう",
            "出よう",
            "移動",
            "案内",
            "海",
            "山",
            "店",
            "外",
            "部屋",
        )
        for message in reversed((context.get("messages") or [])[-4:]):
            if message.get("sender_type") != "character":
                continue
            text = str(message.get("message_text") or "")
            if any(keyword in text for keyword in transition_keywords):
                return True
        return False

    def _is_transition_acceptance(self, user_message_text: str) -> bool:
        text = str(user_message_text or "").strip().lower()
        if not text:
            return False
        positive_keywords = (
            "はい",
            "うん",
            "いいよ",
            "お願い",
            "おねがい",
            "分かった",
            "わかった",
            "行こう",
            "行く",
            "連れて",
            "見せて",
            "進めて",
            "ok",
            "okay",
            "yes",
            "sure",
        )
        return any(keyword in text for keyword in positive_keywords)

    def _should_auto_generate_scene_image(self, before_context: dict, after_context: dict, user_message_text: str) -> bool:
        if not self._recent_character_transition_offer_exists(before_context):
            return False
        if not self._is_transition_acceptance(user_message_text):
            return False
        before = self._state_json_from_context(before_context)
        after = self._state_json_from_context(after_context)
        progression = after.get("scene_progression") or {}
        if progression.get("transition_occurred"):
            return True
        if self._scene_value_changed(before, after, "location"):
            return True
        if self._scene_value_changed(before, after, "background"):
            return True
        return False

    def _extract_state_payload(self, session, context: dict):
        state = self._session_state_service.extract_state(
            session=session,
            messages=context["messages"],
            characters=context["characters"],
        )
        return self._serialize_state(state) if self._serialize_state else state

    def _defer_post_processing_enabled(self) -> bool:
        try:
            return bool(current_app.config.get("LIVE_CHAT_DEFER_POST_PROCESSING", True))
        except RuntimeError:
            return False

    def _run_deferred_post_processing(
        self,
        session_id: int,
        assistant_message_payload: dict | None,
        user_message_text: str,
    ):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        updated_context = self._context_provider(session_id)
        self.update_scene_progression(session_id, updated_context, user_message_text)
        updated_context = self._context_provider(session_id)
        self.update_conversation_director(session_id, updated_context, user_message_text)
        updated_context = self._context_provider(session_id)
        self.update_line_visual_note(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.update_session_memory(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.update_conversation_evaluation(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        if assistant_message_payload:
            assistant_message = SimpleNamespace(**assistant_message_payload)
            self.update_scene_choices(session_id, updated_context, assistant_message)
            updated_context = self._context_provider(session_id)
        if self._letter_service:
            self._update_character_user_memory(session, updated_context)
            self._character_memory_note_service.extract_from_live_chat_context(
                self._text_ai_client,
                updated_context,
                source_ref=f"chat_session:{session_id}",
            )
            return self._letter_service.try_generate_for_context(
                session,
                updated_context,
                trigger_type="conversation",
            )
        return None

    def _schedule_deferred_post_processing(
        self,
        session_id: int,
        assistant_message_payload: dict | None,
        user_message_text: str,
    ):
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            self._run_deferred_post_processing(session_id, assistant_message_payload, user_message_text)
            return False

        def worker():
            with app.app_context():
                try:
                    self._run_deferred_post_processing(session_id, assistant_message_payload, user_message_text)
                except Exception:
                    app.logger.exception("deferred live chat post-processing failed")
                finally:
                    db.session.remove()

        threading.Thread(target=worker, name=f"live-chat-post-process-{session_id}", daemon=True).start()
        return True

    def _schedule_letter_generation(self, session_id: int, context: dict, trigger_type: str) -> bool:
        if not self._letter_service:
            return False
        return self._letter_service.schedule_generate_for_context(
            session_id,
            context,
            trigger_type=trigger_type,
        )

    def post_directed_scene_message(self, session, session_id: int, user_message, intent: dict):
        context = self._context_provider(session_id)
        self.apply_directed_scene(session_id, context, user_message.message_text, intent)
        context = self._context_provider(session_id)
        scene_update = ((context.get("state") or {}).get("state_json") or {}).get("directed_scene") or {}
        reply = text_support.generate_narration_reaction(
            self._text_ai_client,
            context,
            user_message.message_text,
            scene_update,
        )
        assistant_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": reply["speaker_name"],
                "message_text": reply["message_text"],
                "message_role": "assistant",
                "state_snapshot_json": {
                    "input_intent": intent,
                    "directed_scene": scene_update,
                },
            },
        )
        updated_context = self._context_provider(session_id)
        self.update_line_visual_note(session_id, updated_context)
        generated_image = None
        updated_context = self._context_provider(session_id)
        self.update_session_memory(session_id, updated_context)
        self._update_character_user_memory(session, updated_context)
        self._character_memory_note_service.extract_from_live_chat_context(
            self._text_ai_client,
            updated_context,
            source_ref=f"chat_session:{session_id}",
        )
        updated_context = self._context_provider(session_id)
        self.update_conversation_evaluation(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        state = self._extract_state_payload(session, updated_context)
        updated_context = self._context_provider(session_id)
        deferred_letter = self._schedule_letter_generation(session_id, updated_context, "scene_transition")
        return {
            "messages": [self._serialize_message(user_message), self._serialize_message(assistant_message)],
            "state": state,
            "session": updated_context["session"],
            "input_intent": intent,
            "generated_image": generated_image,
            "new_letter": None,
            "deferred_letter": deferred_letter,
        }

    def _serialize_location_for_state(self, location) -> dict:
        return {
            "id": location.id,
            "name": location.name,
            "region": location.region,
            "location_type": location.location_type,
            "description": location.description,
            "image_prompt": location.image_prompt,
            "owner_character_id": location.owner_character_id,
        }

    def _build_location_move_prompt(self, context: dict, location) -> str:
        character_names = "、".join(character.get("name") or "" for character in context.get("characters") or [])
        recent_lines = []
        for message in (context.get("messages") or [])[-6:]:
            speaker = message.get("speaker_name") or message.get("sender_type") or ""
            text = message.get("message_text") or ""
            if text:
                recent_lines.append(f"{speaker}: {text}")
        lines = [
            "ライブチャットの場所移動イベントCG。",
            "プレイヤー視点ではなく、キャラクターたちがその施設に到着した瞬間を見せる。",
            "登録済みキャラクターの顔、髪型、衣装の印象、画風の連続性を保つ。",
            "画像内に文字、ロゴ、字幕、吹き出し、UI、看板の可読文字を入れない。",
            f"移動先施設: {location.name or ''}",
            f"地域: {location.region or ''}",
            f"施設タイプ: {location.location_type or ''}",
            f"施設説明: {location.description or ''}",
            f"施設画像方針: {location.image_prompt or ''}",
            f"登場キャラクター: {character_names}",
            "会話の直前ログ:",
            *recent_lines,
            "演出: 場所の特徴が一目でわかり、キャラクターがそこで会話を始めたくなる空気を作る。",
        ]
        prompt = "\n".join(lines)
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        prompt = prompt_support.apply_visual_style(prompt, context)
        return prompt_support.forbid_text_in_image(prompt)

    def move_to_location(self, session_id: int, location_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        location = self._world_location_repository.get(location_id)
        if not location or location.project_id != session.project_id:
            raise ValueError("location_id is invalid")

        context = self._context_provider(session_id)
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        location_payload = self._serialize_location_for_state(location)
        focus_summary = f"{location.name}へ移動した。{(location.description or '')[:180]}"
        prompt = self._build_location_move_prompt(context, location)
        scene_update = {
            "scene_phase": "location_move",
            "location": location.name,
            "background": location.description or location.image_prompt or location.name,
            "focus_summary": focus_summary,
            "next_topic": f"{location.name}で、施設の雰囲気やそこで起きそうな出来事を会話に混ぜる",
            "transition_occurred": True,
            "character_reaction_hint": "移動先の施設説明を理解し、その場所らしい感情・提案・小さな事件の火種を出す",
            "image_focus": prompt,
            "selected_location": location_payload,
        }
        state_json["current_location"] = location_payload
        state_json["location"] = location.name
        state_json["background"] = location.description or location.image_prompt or location.name
        state_json["scene_progression"] = scene_update
        state_json["directed_scene"] = scene_update
        state_json["visual_prompt_text"] = prompt
        self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "narration_note": focus_summary,
                "visual_prompt_text": prompt,
            },
        )

        user_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "narration",
                "speaker_name": "移動",
                "message_text": f"{location.name}へ移動した。",
                "message_role": "location_move",
                "state_snapshot_json": {
                    "location_move": location_payload,
                    "directed_scene": scene_update,
                },
            },
        )

        generated_image = None
        image_generation_error = None
        try:
            generated_image = self._media_service.generate_image(
                session_id,
                {
                    "image_type": "location_move",
                    "prompt_text": prompt,
                    "use_existing_prompt": True,
                    "size": payload.get("size") or UserSettingService.DEFAULTS.get("default_size", "1536x1024"),
                    "quality": payload.get("quality") or "low",
                },
            )
        except Exception as exc:
            current_app.logger.exception("location move image generation failed")
            image_generation_error = str(exc)

        updated_context = self._context_provider(session_id)
        reply = text_support.generate_narration_reaction(
            self._text_ai_client,
            updated_context,
            f"{location.name}へ移動した。",
            scene_update,
        )
        assistant_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": reply["speaker_name"],
                "message_text": reply["message_text"],
                "message_role": "assistant",
                "state_snapshot_json": {
                    "location_move": location_payload,
                    "directed_scene": scene_update,
                },
            },
        )
        updated_context = self._context_provider(session_id)
        self.update_line_visual_note(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.update_session_memory(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.update_conversation_evaluation(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self._update_character_user_memory(session, updated_context)
        self._character_memory_note_service.extract_from_live_chat_context(
            self._text_ai_client,
            updated_context,
            source_ref=f"chat_session:{session_id}",
        )
        updated_context = self._context_provider(session_id)
        return {
            "location": location_payload,
            "generated_image": generated_image,
            "image_generation_error": image_generation_error,
            "messages": [self._serialize_message(user_message), self._serialize_message(assistant_message)],
            "context": updated_context,
        }

    def _build_lccd_photo_prompt(self, context: dict, instruction: str, pose_style: str, costume_image) -> str:
        characters = context.get("characters") or []
        character = characters[0] if characters else {}
        state_json = (context.get("state") or {}).get("state_json") or {}
        current_location = state_json.get("current_location") or {}
        costume_state = costume_image.get("state_json") if isinstance(costume_image, dict) else {}
        costume_prompt = costume_image.get("prompt_text") if isinstance(costume_image, dict) else ""
        costume_notes = "\n".join(
            str(part or "").strip()
            for part in [
                instruction,
                costume_state.get("instruction") if isinstance(costume_state, dict) else "",
                costume_state.get("rewritten_instruction") if isinstance(costume_state, dict) else "",
                costume_prompt,
            ]
            if str(part or "").strip()
        )
        prompt = "\n".join(
            [
                "This image is the live-chat story display photo only. It is not a closet reference image.",
                "Set the background in a cyber-feeling apparel shop interior: luminous clothing racks, smart mirrors, fitting-room doors, glossy floor, neon accent lights, and a boutique photo-shoot corner. The exact previous background does not need to match.",
                "Do not use a plain studio, blank wall, outdoor background, bedroom, generic room, or simple reference-image background for this story display photo.",
                "The character must take an attractive fashion photo pose, not a stiff standing pose: use a graceful S-curve, one hand near hair or collar, playful turn, confident hip shift, stepping pose, mirror pose, or magazine-style pose that matches the character.",
                "Make the pose expressive and charming while preserving the outfit design from the newly generated costume reference image.",
                "Do not use or imitate the closet reference image composition: no straight front-facing pose, no catalog camera angle, no plain composition, no neutral expression.",
                "The final image must look like a realistic fashion editorial photo inside the apparel shop: cinematic lighting, natural body weight shift, expressive face, believable fabric movement, and a posed model-shoot composition.",
                "Use the newly generated apparel-shop background image as the primary scene base. The final background must be the cyber apparel shop interior.",
                "Use the newly generated costume reference image only for the character identity, face, hair, body type, art style, and outfit design. Never copy its gray/plain background.",
                "If the two reference images conflict, prioritize the apparel-shop background image for the environment and the costume reference image only for the character and outfit.",
                "If the result looks like a plain gray reference sheet, catalog full-body image, or background-only swap, it is invalid.",
                "お着替えモードの写真撮影。ビジュアルノベルの鑑賞用イベントCG。",
                "サイバー感のあるアパレル店内で、キャラクターがモデルのようなポーズで立つ。",
                "背景は厳密に同じ店内でなくてよい。アパレルショップだと分かるラック、鏡、試着室、ネオン照明を入れる。",
                "衣装基準画像の構図は使わない。衣装の内容はユーザーの衣装相談と保存済み衣装メモのテキストから反映する。",
                "保存用の全身衣装カタログではなく、会話画面で映えるポーズ、表情、ライティング、背景を重視する。",
                "衣装基準画像の正面棒立ち、無表情、単純な全身カタログ構図、同じカメラ角度をコピーしない。",
                "モデル撮影としてリアリティのあるポーズにする。重心移動、肩や腰の角度、手の置き方、視線、布の揺れ、店内照明を使った立体感を必ず入れる。",
                "衣装基準画像のグレー背景や単色背景は絶対に使わない。背景は必ずサイバー感のあるアパレルショップ店内にする。",
                "背景参照画像を最優先し、衣装基準画像からはキャラクターと衣装だけを抜き出して使う。",
                "ただし顔、髪型、体格、画風、衣装の形状、色、素材感、装飾は変えない。",
                "背景はラプラスシティのお着替えルーム兼撮影ブース。試着室、ラック、鏡、柔らかい照明、近未来ファッションスタジオ。",
                "画像内に文字、ロゴ、字幕、吹き出し、UI、看板の可読文字を入れない。",
                f"キャラクター: {character.get('name') or ''}",
                f"キャラクター外見: {character.get('appearance_summary') or ''}",
                f"キャラクター性格: {character.get('personality') or ''}",
                f"ユーザーの衣装相談: {instruction}",
                f"保存済み衣装メモ: {costume_notes[:1800]}",
                f"撮影ポーズ方針: {pose_style or '衣装相談の文脈から、キャラクターらしい撮影ポーズを自動で決める'}",
                "衣装相談にポーズ、雰囲気、距離感、撮影場所の希望が含まれている場合は、それを撮影カットに反映する。",
                f"直前の現在地: {current_location.get('name') or state_json.get('location') or ''}",
                f"衣装基準画像ID: {(costume_image or {}).get('id') if isinstance(costume_image, dict) else getattr(costume_image, 'id', '') if costume_image else ''}",
            ]
        )
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        prompt = prompt_support.apply_visual_style(prompt, context)
        return prompt_support.forbid_text_in_image(prompt)

    def _build_lccd_background_prompt(self, context: dict, instruction: str) -> str:
        prompt = "\n".join(
            [
                "Live-chat dress-up mode background plate only.",
                "Create a cyber-feeling apparel shop interior for a visual novel scene.",
                "No character, no person, no mannequin as the main subject.",
                "Include luminous clothing racks, smart mirrors, fitting-room doors, glossy floor, neon accent lights, soft boutique lighting, and a photo-shoot corner.",
                "This background will be used as a reference image for a later character fashion photo.",
                "Do not use a plain gray studio, blank wall, bedroom, outdoor street, or generic empty room.",
                "No readable text, no logo, no subtitles, no UI.",
                "サイバー感のあるアパレルショップ店内。衣装ラック、鏡、試着室、ネオン照明、撮影ブースが見える背景。",
                "キャラクターは描かない。背景だけを作る。",
                f"衣装相談の雰囲気: {instruction[:500]}",
            ]
        )
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        prompt = prompt_support.apply_visual_style(prompt, context)
        return prompt_support.forbid_text_in_image(prompt)

    def _build_lccd_costume_scene_prompt(self, context: dict, instruction: str, costume_image) -> str:
        characters = context.get("characters") or []
        character = characters[0] if characters else {}
        costume_state = costume_image.get("state_json") if isinstance(costume_image, dict) else {}
        costume_notes = "\n".join(
            str(part or "").strip()
            for part in [
                instruction,
                costume_state.get("instruction") if isinstance(costume_state, dict) else "",
                costume_state.get("rewritten_instruction") if isinstance(costume_state, dict) else "",
            ]
            if str(part or "").strip()
        )
        prompt = "\n".join(
            [
                "Edit the provided costume reference image into a live-chat display source image.",
                "Keep the same character identity, face, hair, body type, art style, and outfit design from the reference image.",
                "Change the plain or gray reference background into a cyber-feeling apparel shop interior.",
                "The new background must include luminous clothing racks, smart mirrors, fitting-room doors, glossy floor, neon accent lights, and a boutique photo-shoot corner.",
                "Do not keep the plain studio background. Do not use a blank wall or gray backdrop.",
                "Keep a simple full-body or near full-body composition for this intermediate source image. This is not the final posed photo.",
                "No readable text, logo, subtitles, UI, or sign text in the image.",
                "衣装参照画像のキャラクター、顔、髪型、体型、画風、衣装デザインを維持する。",
                "背景だけをサイバー感のあるアパレルショップ店内に変更する。",
                "グレー背景、単色背景、無地スタジオ背景は禁止。",
                "店内には衣装ラック、スマートミラー、試着室、ネオン照明、撮影ブースを入れる。",
                f"キャラクター: {character.get('name') or ''}",
                f"キャラクター外見: {character.get('appearance_summary') or ''}",
                f"衣装メモ: {costume_notes[:1600]}",
            ]
        )
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        prompt = prompt_support.apply_visual_style(prompt, context)
        return prompt_support.forbid_text_in_image(prompt)

    def _build_lccd_pose_from_costume_scene_prompt(self, context: dict, instruction: str, pose_style: str) -> str:
        characters = context.get("characters") or []
        character = characters[0] if characters else {}
        prompt = "\n".join(
            [
                "Create the final live-chat story display photo from the provided source image.",
                "Use the provided image as the only visual reference.",
                "Keep the same character identity, face, hair, body type, art style, outfit design, and cyber apparel shop background.",
                "Change mainly the pose, expression, camera angle, and fashion-photo composition.",
                "The character must take an attractive model pose, not a stiff front-facing catalog pose.",
                "Use a graceful S-curve, confident hip shift, one hand near hair or collar, slight turn, stepping pose, mirror pose, or magazine-style fashion pose.",
                "Keep the cyber apparel shop interior visible behind the character. Do not replace it with a gray or plain background.",
                "This is a visual novel event CG for the chat screen, not a closet reference image.",
                "No readable text, logo, subtitles, UI, or sign text in the image.",
                "参照画像と同じキャラクター、同じ衣装、同じサイバー感のあるアパレルショップ店内を維持する。",
                "変更するのは主にポーズ、表情、カメラ角度、構図。",
                "正面棒立ちの衣装カタログではなく、モデル撮影らしい魅力的なポーズにする。",
                "背景をグレーや単色に戻さない。必ずアパレルショップ店内を残す。",
                f"キャラクター: {character.get('name') or ''}",
                f"ユーザーの衣装相談: {instruction}",
                f"ポーズ方針: {pose_style or '衣装とキャラクター性に合うモデルポーズを自動で決める'}",
            ]
        )
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        prompt = prompt_support.apply_visual_style(prompt, context)
        return prompt_support.forbid_text_in_image(prompt)

    def _build_photo_mode_prompt(self, context: dict, instruction: str, pose_style: str) -> str:
        characters = context.get("characters") or []
        character = characters[0] if characters else {}
        state_json = (context.get("state") or {}).get("state_json") or {}
        current_location = state_json.get("current_location") or {}
        displayed_observation = state_json.get("displayed_image_observation") or {}
        prompt = "\n".join(
            [
                "撮影モードのライブチャット表示用イベントCG。",
                "現在表示されている画像を背景・場所・光・雰囲気の最優先リファレンスとして使う。",
                "衣装は現在選択中の衣装をそのまま維持する。衣装デザイン、色、素材、装飾を変更しない。",
                "変更するのは主にキャラクターのポーズ、表情、立ち位置、カメラ距離、構図のみ。",
                "背景を別の場所に変えない。現在の表示画像と同じ場所で撮影し直したように見せる。",
                "画像内に文字、ロゴ、字幕、吹き出し、UI、看板の可読文字を入れない。",
                f"キャラクター: {character.get('name') or ''}",
                f"キャラクター外見: {character.get('appearance_summary') or ''}",
                f"キャラクター性格: {character.get('personality') or ''}",
                f"現在地: {current_location.get('name') or state_json.get('location') or ''}",
                f"現在表示画像の観察メモ: {displayed_observation}",
                f"ユーザーの撮影指示: {instruction}",
                f"ポーズ・構図方針: {pose_style or 'ユーザー指示をもとに、キャラクターらしい魅力的なポーズと構図にする'}",
            ]
        )
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        prompt = prompt_support.apply_visual_style(prompt, context)
        return prompt_support.forbid_text_in_image(prompt)

    def _lccd_location_payload(self, context: dict) -> dict:
        character = (context.get("characters") or [{}])[0]
        return {
            "id": "lccd",
            "name": "お着替え",
            "region": "Laplace City",
            "location_type": "apparel_shop_photo_studio",
            "description": "衣装相談、試着、撮影ができるお着替えルーム。キャラクターと一緒に似合う衣装を考え、着替えた姿を撮影する場所。",
            "image_prompt": "near-future apparel shop and fashion photo studio, fitting room, mirrors, clothing racks, soft neon lighting",
            "owner_character_id": character.get("id"),
        }

    def _build_lccd_room_prompt(self, context: dict, location_payload: dict) -> str:
        character_names = "、".join(character.get("name") or "" for character in context.get("characters") or [])
        prompt = "\n".join(
            [
                "ライブチャットの場所移動イベントCG。",
                "キャラクターと一緒にサイバーなアパレルショップ店内に移動した場面。",
                "近未来の公式アパレルショップ兼フォトスタジオ。試着室、衣装ラック、大きな鏡、撮影ライト、柔らかいネオン照明。",
                "キャラクターは現在の衣装のまま登場する。新しい衣装への着替えや衣装差分はまだ描かない。",
                "キャラクターは棒立ちではなく、店内を案内するような自然で魅力的なポーズ。軽く振り向く、手を差し出す、鏡や衣装ラックを示すなど、会話が始まる瞬間にする。",
                "全身カタログ写真ではなく、背景とキャラクターが馴染むノベルゲームのシーンCG。",
                "ここでは移動先のシーンだけを作る。衣装生成や撮影は、ユーザーが次のメッセージで希望を送ってから始める。",
                "画像内に文字、ロゴ、字幕、吹き出し、UI、看板の可読文字を入れない。",
                f"施設名: {location_payload.get('name') or ''}",
                f"施設説明: {location_payload.get('description') or ''}",
                f"登場キャラクター: {character_names}",
            ]
        )
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        prompt = prompt_support.apply_visual_style(prompt, context)
        return prompt_support.forbid_text_in_image(prompt)

    def enter_lccd_room(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        context = self._context_provider(session_id)
        location_payload = self._lccd_location_payload(context)
        prompt = self._build_lccd_room_prompt(context, location_payload)
        scene_update = {
            "scene_phase": "dress_up_room",
            "location": location_payload["name"],
            "background": location_payload["description"],
            "focus_summary": "お着替えルームへ移動した。ここでキャラクター自身が着る衣装をユーザーと一緒に考える。",
            "next_topic": "キャラクターが自分に似合う衣装や自分が着る服について相談し、ユーザーに一緒に選んでほしいと頼む",
            "transition_occurred": True,
            "character_reaction_hint": (
                "ユーザーを着替えさせるのではなく、キャラクター自身が着替える前提で話す。"
                "「あなたに似合う衣装」「あなたが着る服」とは絶対に言わない。"
                "「私に似合う衣装、一緒に考えてくれる？」「私が着る服、どんなのがいいと思う？」のように誘う。"
            ),
            "image_focus": prompt,
            "selected_location": location_payload,
        }
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json["current_location"] = location_payload
        state_json["location"] = location_payload["name"]
        state_json["background"] = location_payload["description"]
        state_json["scene_progression"] = scene_update
        state_json["directed_scene"] = scene_update
        state_json["visual_prompt_text"] = prompt
        state_json["lccd_ready"] = True
        self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "narration_note": scene_update["focus_summary"],
                "visual_prompt_text": prompt,
            },
        )
        user_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "narration",
                "speaker_name": "移動",
                "message_text": "お着替えルームへ移動した。",
                "message_role": "lccd_enter",
                "state_snapshot_json": {"location_move": location_payload, "directed_scene": scene_update},
            },
        )
        generated_image = None
        image_generation_error = None
        try:
            generated_image = self._media_service.generate_image(
                session_id,
                {
                    "image_type": "dress_up_room",
                    "prompt_text": prompt,
                    "use_existing_prompt": True,
                    "size": payload.get("size") or UserSettingService.DEFAULTS.get("default_size", "1536x1024"),
                    "quality": payload.get("quality") or "low",
                },
            )
        except Exception as exc:
            current_app.logger.exception("dress up room image generation failed")
            image_generation_error = str(exc)
        intro_reply = text_support.generate_narration_reaction(
            self._text_ai_client,
            self._context_provider(session_id),
            (
                "お着替えルームへ移動した。"
                "ここではユーザーではなくキャラクター自身が着替える。"
                "キャラクターは『私に似合う衣装、一緒に考えてくれる？』という方向で話す。"
            ),
            scene_update,
        )
        assistant_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": intro_reply["speaker_name"],
                "message_text": intro_reply["message_text"],
                "message_role": "assistant",
                "state_snapshot_json": {"lccd": True, "phase": "enter", "directed_scene": scene_update},
            },
        )
        updated_context = self._context_provider(session_id)
        self.update_line_visual_note(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        return {
            "location": location_payload,
            "generated_image": generated_image,
            "image_generation_error": image_generation_error,
            "messages": [self._serialize_message(user_message), self._serialize_message(assistant_message)],
            "context": updated_context,
        }

    def generate_lccd_photo_shoot(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        instruction = str(payload.get("prompt_text") or "").strip()
        if not instruction:
            raise ValueError("prompt_text is required")
        pose_style = str(payload.get("pose_style") or "").strip()
        mode = str(payload.get("mode") or "combined").strip().lower()

        context = self._context_provider(session_id)
        character = (context.get("characters") or [{}])[0]
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        if mode in {"photo", "photo_only", "shoot", "shoot_only"}:
            current_location = state_json.get("current_location") or {}
            scene_update = {
                "scene_phase": "photo_mode_shoot",
                "location": current_location.get("name") or state_json.get("location") or "",
                "background": state_json.get("background") or current_location.get("description") or "",
                "focus_summary": f"撮影モードで、現在のシーンを背景にポーズと構図を撮り直す。撮影指示: {instruction[:180]}",
                "next_topic": "現在の場面と衣装を保ったまま、撮影カットの感想を話す",
                "transition_occurred": False,
                "character_reaction_hint": "場所や衣装は変えず、今いるシーンで撮影し直す流れにする",
            }
            state_json["scene_progression"] = scene_update
            state_json["directed_scene"] = scene_update
            self._session_state_service.upsert_state(
                session_id,
                {
                    "state_json": state_json,
                    "narration_note": scene_update["focus_summary"],
                },
            )
            opening_message = self._chat_message_service.create_message(
                session_id,
                {
                    "sender_type": "user",
                    "speaker_name": session.player_name or "プレイヤー",
                    "message_text": instruction,
                    "message_role": "player",
                    "state_snapshot_json": {"directed_scene": scene_update, "photo_mode": True},
                },
            )
            thinking_reply = text_support.generate_narration_reaction(
                self._text_ai_client,
                self._context_provider(session_id),
                f"撮影モードで、現在のシーンのまま撮影する。指示: {instruction}",
                scene_update,
            )
            thinking_message = self._chat_message_service.create_message(
                session_id,
                {
                    "sender_type": "character",
                    "speaker_name": thinking_reply["speaker_name"],
                    "message_text": thinking_reply["message_text"],
                    "message_role": "assistant",
                    "state_snapshot_json": {"photo_mode": True, "phase": "consultation"},
                },
            )
            photo_prompt = self._build_photo_mode_prompt(
                self._context_provider(session_id),
                instruction,
                pose_style,
            )
            state_row = self._session_state_service.get_state(session_id)
            state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
            state_json["visual_prompt_text"] = photo_prompt
            state_json["photo_mode_shoot"] = {
                "instruction": instruction,
                "pose_style": pose_style,
                "use_current_scene_as_background": True,
            }
            self._session_state_service.upsert_state(
                session_id,
                {
                    "state_json": state_json,
                    "visual_prompt_text": photo_prompt,
                },
            )
            photo_image = self._media_service.generate_image(
                session_id,
                {
                    "image_type": "photo_mode_shoot",
                    "prompt_text": photo_prompt,
                    "use_existing_prompt": True,
                    "use_selected_scene_as_reference": True,
                    "size": payload.get("photo_size") or payload.get("size") or "1536x1024",
                    "quality": payload.get("photo_quality") or payload.get("quality") or "low",
                    "model": payload.get("model") or payload.get("image_ai_model"),
                    "provider": payload.get("provider") or payload.get("image_ai_provider"),
                },
            )
            finish_message = self._chat_message_service.create_message(
                session_id,
                {
                    "sender_type": "character",
                    "speaker_name": thinking_reply["speaker_name"],
                    "message_text": "撮影してきたよ。衣装はそのまま、今の場面でポーズと構図だけ変えてみた。",
                    "message_role": "assistant",
                    "state_snapshot_json": {
                        "photo_mode": True,
                        "phase": "finished",
                        "photo_image_id": (photo_image or {}).get("id"),
                    },
                },
            )
            updated_context = self._context_provider(session_id)
            return {
                "costume_image": None,
                "photo_image": photo_image,
                "photo_generation_error": None,
                "messages": [
                    self._serialize_message(opening_message),
                    self._serialize_message(thinking_message),
                    self._serialize_message(finish_message),
                ],
                "context": updated_context,
            }
        lccd_location = self._lccd_location_payload(context)
        scene_update = {
            "scene_phase": "lccd_photo_shoot",
            "location": lccd_location["name"],
            "background": lccd_location["description"],
            "focus_summary": f"お着替えで衣装相談をして撮影する。衣装希望: {instruction[:180]}",
            "next_topic": "衣装を一緒に考え、着替えと撮影カットの感想を話す",
            "transition_occurred": True,
            "character_reaction_hint": "ユーザーの衣装希望を聞いて、似合う方向性と撮影ポーズを一緒に考え、着替えてくる流れにする",
        }
        state_json["current_location"] = lccd_location
        state_json["location"] = lccd_location["name"]
        state_json["background"] = lccd_location["description"]
        state_json["scene_progression"] = scene_update
        state_json["directed_scene"] = scene_update
        self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "narration_note": scene_update["focus_summary"],
            },
        )

        opening_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "user",
                "speaker_name": session.player_name or "プレイヤー",
                "message_text": instruction,
                "message_role": "player",
                "state_snapshot_json": {"directed_scene": scene_update, "lccd": True},
            },
        )
        thinking_reply = text_support.generate_narration_reaction(
            self._text_ai_client,
            self._context_provider(session_id),
            f"お着替えで衣装相談をする。希望: {instruction}",
            scene_update,
        )
        thinking_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": thinking_reply["speaker_name"],
                "message_text": thinking_reply["message_text"],
                "message_role": "assistant",
                "state_snapshot_json": {"lccd": True, "phase": "consultation"},
            },
        )

        if mode in {"photo", "photo_only", "shoot", "shoot_only"}:
            photo_prompt = self._build_photo_mode_prompt(
                self._context_provider(session_id),
                instruction,
                pose_style,
            )
            state_row = self._session_state_service.get_state(session_id)
            state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
            state_json["visual_prompt_text"] = photo_prompt
            state_json["photo_mode_shoot"] = {
                "instruction": instruction,
                "pose_style": pose_style,
                "use_current_scene_as_background": True,
            }
            self._session_state_service.upsert_state(
                session_id,
                {
                    "state_json": state_json,
                    "visual_prompt_text": photo_prompt,
                },
            )
            photo_image = self._media_service.generate_image(
                session_id,
                {
                    "image_type": "photo_mode_shoot",
                    "prompt_text": photo_prompt,
                    "use_existing_prompt": True,
                    "use_selected_scene_as_reference": True,
                    "size": payload.get("photo_size") or payload.get("size") or "1536x1024",
                    "quality": payload.get("photo_quality") or payload.get("quality") or "low",
                    "model": payload.get("model") or payload.get("image_ai_model"),
                    "provider": payload.get("provider") or payload.get("image_ai_provider"),
                },
            )
            finish_message = self._chat_message_service.create_message(
                session_id,
                {
                    "sender_type": "character",
                    "speaker_name": thinking_reply["speaker_name"],
                    "message_text": "撮影してきたよ。衣装はそのまま、今の場面でポーズと構図だけ変えてみた。",
                    "message_role": "assistant",
                    "state_snapshot_json": {
                        "photo_mode": True,
                        "phase": "finished",
                        "photo_image_id": (photo_image or {}).get("id"),
                    },
                },
            )
            updated_context = self._context_provider(session_id)
            return {
                "costume_image": None,
                "photo_image": photo_image,
                "photo_generation_error": None,
                "messages": [
                    self._serialize_message(opening_message),
                    self._serialize_message(thinking_message),
                    self._serialize_message(finish_message),
                ],
                "context": updated_context,
            }

        costume_instruction = "\n".join(
            [
                "お着替えで相談して決めた衣装。",
                "クローゼット保存用なので、衣装の全体像と構造が分かる正面1枚の衣装基準画像にする。",
                "必ず一人のキャラクターを正面向きで1回だけ描く。複数ポーズ、4分割、ターンアラウンド、背面図、側面図、コマ割り、比較表は禁止。",
                "ユーザー指示に「回って」「くるっと」「ポーズ」「撮影」などの演出が含まれていても、保存用衣装基準画像では無視し、衣装デザインだけを抽出する。",
                "背景はシンプルにして、衣装再利用のリファレンスとして使いやすくする。",
                instruction,
            ]
        )
        costume_image = self._media_service.generate_costume(
            session_id,
            {
                "prompt_text": costume_instruction,
                "size": payload.get("costume_size") or "1024x1536",
                "quality": payload.get("costume_quality") or payload.get("quality") or "medium",
                "model": payload.get("model") or payload.get("image_ai_model"),
                "provider": payload.get("provider") or payload.get("image_ai_provider"),
                "save_to_closet": True,
                "outfit_name": payload.get("outfit_name") or f"お着替え {character.get('name') or 'outfit'}",
                "outfit_description": instruction,
                "usage_scene": "お着替え撮影",
                "mood": pose_style or "photo shoot",
            },
        )

        if mode in {"costume", "costume_only", "dress", "dress_only"}:
            finish_message = self._chat_message_service.create_message(
                session_id,
                {
                    "sender_type": "character",
                    "speaker_name": thinking_reply["speaker_name"],
                    "message_text": "着替えてきたよ。衣装は保存して、今のアクティブ衣装にしておいたよ。",
                    "message_role": "assistant",
                    "state_snapshot_json": {
                        "lccd": True,
                        "phase": "costume_finished",
                        "costume_image_id": (costume_image or {}).get("id"),
                    },
                },
            )
            updated_context = self._context_provider(session_id)
            return {
                "costume_image": costume_image,
                "photo_image": None,
                "photo_generation_error": None,
                "messages": [
                    self._serialize_message(opening_message),
                    self._serialize_message(thinking_message),
                    self._serialize_message(finish_message),
                ],
                "context": updated_context,
            }

        photo_context = self._context_provider(session_id)
        costume_scene_prompt = self._build_lccd_costume_scene_prompt(photo_context, instruction, costume_image)
        costume_scene_image = None
        costume_scene_generation_error = None
        try:
            costume_scene_image = self._media_service.generate_image(
                session_id,
                {
                    "image_type": "dress_up_costume_scene",
                    "prompt_text": costume_scene_prompt,
                    "use_existing_prompt": True,
                    "reference_asset_ids": [(costume_image or {}).get("asset_id")],
                    "skip_character_references": True,
                    "skip_outfit_prompt": True,
                    "input_fidelity": "high",
                    "size": payload.get("scene_size") or payload.get("photo_size") or payload.get("size") or "1536x1024",
                    "quality": payload.get("scene_quality") or payload.get("photo_quality") or payload.get("quality") or "low",
                    "model": payload.get("model") or payload.get("image_ai_model"),
                    "provider": payload.get("provider") or payload.get("image_ai_provider"),
                },
            )
        except Exception as exc:
            current_app.logger.exception("dress up costume scene image generation failed")
            costume_scene_generation_error = str(exc)

        photo_prompt = self._build_lccd_pose_from_costume_scene_prompt(
            self._context_provider(session_id),
            instruction,
            pose_style,
        )
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json["visual_prompt_text"] = photo_prompt
        state_json["lccd_photo_shoot"] = {
            "instruction": instruction,
            "pose_style": pose_style,
            "costume_image_id": (costume_image or {}).get("id"),
            "costume_scene_image_id": (costume_scene_image or {}).get("id"),
            "costume_scene_generation_error": costume_scene_generation_error,
        }
        self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "visual_prompt_text": photo_prompt,
            },
        )
        photo_image = None
        photo_generation_error = None
        try:
            reference_asset_ids = [
                (costume_scene_image or {}).get("asset_id"),
            ]
            reference_asset_ids = [asset_id for asset_id in reference_asset_ids if asset_id]
            photo_image = self._media_service.generate_image(
                session_id,
                {
                    "image_type": "dress_up_photo_shoot",
                    "prompt_text": photo_prompt,
                    "use_existing_prompt": True,
                    "reference_asset_ids": reference_asset_ids,
                    "skip_character_references": True,
                    "skip_outfit_prompt": True,
                    "input_fidelity": "low",
                    "size": payload.get("photo_size") or payload.get("size") or "1536x1024",
                    "quality": payload.get("photo_quality") or payload.get("quality") or "low",
                    "model": payload.get("model") or payload.get("image_ai_model"),
                    "provider": payload.get("provider") or payload.get("image_ai_provider"),
                },
            )
        except Exception as exc:
            current_app.logger.exception("dress up photo shoot image generation failed")
            photo_generation_error = str(exc)
        if photo_image:
            self._media_service.select_image(photo_image["id"], update_observation=False, session_id=session_id)
        finish_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": thinking_reply["speaker_name"],
                "message_text": (
                    "着替えてきたよ。どうかな、この感じ。撮影用に少しポーズも作ってみた。"
                    if photo_image
                    else "衣装案は保存できたけど、会話画面用の撮影カットは失敗しちゃったみたい。もう一度撮影してみる？"
                ),
                "message_role": "assistant",
                "state_snapshot_json": {
                    "lccd": True,
                    "phase": "finished",
                    "costume_image_id": (costume_image or {}).get("id"),
                    "photo_image_id": (photo_image or {}).get("id"),
                },
            },
        )
        updated_context = self._context_provider(session_id)
        return {
            "costume_image": costume_image,
            "photo_image": photo_image,
            "photo_generation_error": photo_generation_error,
            "messages": [
                self._serialize_message(opening_message),
                self._serialize_message(thinking_message),
                self._serialize_message(finish_message),
            ],
            "context": updated_context,
        }

    def post_message(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        initial_context = self._context_provider(session_id)
        raw_message_text = str(payload.get("message_text") or "").strip()
        player_proxy_generated = not raw_message_text
        message_text = raw_message_text
        if player_proxy_generated:
            message_text = text_support.generate_player_proxy_message(self._text_ai_client, initial_context)
        forced_intent = str(payload.get("input_intent") or "").strip()
        if forced_intent in {"dialogue", "narration", "visual_request"}:
            input_intent = {
                "intent": forced_intent,
                "reason": "forced by client",
                "should_generate_image": forced_intent in {"narration", "visual_request"},
            }
        else:
            input_intent = text_support.classify_user_input(self._text_ai_client, initial_context, message_text)
        is_directed_scene = input_intent.get("intent") in {"narration", "visual_request"}
        user_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "narration" if is_directed_scene else payload.get("sender_type") or "user",
                "speaker_name": "ナレーション" if is_directed_scene else payload.get("speaker_name") or session.player_name or "プレイヤー",
                "message_text": message_text,
                "message_role": "narration" if is_directed_scene else "player",
                "state_snapshot_json": {
                    "input_intent": input_intent,
                    "player_proxy_generated": player_proxy_generated,
                },
            },
        )
        if is_directed_scene:
            return self.post_directed_scene_message(session, session_id, user_message, input_intent)

        created = [self._serialize_message(user_message)]
        defer_post_processing = self._defer_post_processing_enabled()
        context_before_progression = self._context_provider(session_id)
        context = context_before_progression
        if not defer_post_processing:
            self.update_scene_progression(session_id, context, user_message.message_text)
            context = self._context_provider(session_id)
            self.update_conversation_director(session_id, context, user_message.message_text)
            context = self._context_provider(session_id)
        auto_reply = str(payload.get("auto_reply", "true")).lower() not in {"0", "false", "no", "off"}
        assistant_message = None
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
        updated_context = self._context_provider(session_id)
        self.update_line_visual_note(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        generated_image = None
        image_generation_error = None
        auto_image_candidate = False
        state = self._extract_state_payload(session, updated_context)
        assistant_payload = (
            {
                "id": assistant_message.id,
                "speaker_name": assistant_message.speaker_name,
                "message_text": assistant_message.message_text,
            }
            if assistant_message
            else None
        )
        deferred_processing = False
        deferred_letter = False
        new_letter = None
        if defer_post_processing:
            deferred_processing = self._schedule_deferred_post_processing(
                session_id,
                assistant_payload,
                user_message.message_text,
            )
        else:
            self.update_line_visual_note(session_id, updated_context)
            updated_context = self._context_provider(session_id)
            self.update_session_memory(session_id, updated_context)
            updated_context = self._context_provider(session_id)
            self.update_conversation_evaluation(session_id, updated_context)
            updated_context = self._context_provider(session_id)
            self._update_character_user_memory(session, updated_context)
            self._character_memory_note_service.extract_from_live_chat_context(
                self._text_ai_client,
                updated_context,
                source_ref=f"chat_session:{session_id}",
            )
            state = self._extract_state_payload(session, updated_context)
            updated_context = self._context_provider(session_id)
            if assistant_message:
                self.update_scene_choices(session_id, updated_context, assistant_message)
                updated_context = self._context_provider(session_id)
            deferred_letter = self._schedule_letter_generation(session_id, updated_context, "conversation")
        return {
            "messages": created,
            "state": state,
            "session": updated_context["session"],
            "input_intent": input_intent,
            "generated_image": generated_image,
            "image_generation_error": image_generation_error,
            "auto_image_candidate": bool(auto_image_candidate),
            "new_letter": new_letter,
            "deferred_letter": deferred_letter if not defer_post_processing else False,
            "deferred_processing": deferred_processing,
        }

    def generate_player_proxy_message(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        context = self._context_provider(session_id)
        message_text = text_support.generate_player_proxy_message(self._text_ai_client, context)
        return {
            "message_text": message_text,
            "player_name": session.player_name or "プレイヤー",
        }

    def post_idle_character_message(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        context = self._context_provider(session_id)
        reply = text_support.generate_idle_character_message(self._text_ai_client, context)
        assistant_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": reply["speaker_name"],
                "message_text": reply["message_text"],
                "message_role": "assistant",
                "state_snapshot_json": {"idle_generated": True},
            },
        )
        created = [self._serialize_message(assistant_message)]
        updated_context = self._context_provider(session_id)
        self.update_line_visual_note(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.update_session_memory(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.update_conversation_evaluation(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.update_scene_choices(session_id, updated_context, assistant_message)
        updated_context = self._context_provider(session_id)
        return {
            "messages": created,
            "state": self._extract_state_payload(session, updated_context),
            "session": updated_context["session"],
            "context": updated_context,
            "idle_generated": True,
        }

    def execute_scene_choice(self, session_id: int, choice_id: str, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        scene_choices = state_json.get("scene_choices") or {}
        choices = scene_choices.get("choices") or []
        choice = next((item for item in choices if str(item.get("id")) == str(choice_id)), None)
        if not choice:
            return None

        context = self._context_provider(session_id)
        execution = text_support.generate_choice_execution(self._text_ai_client, context, choice)
        directed_choice = {**choice}
        for key in ("scene_instruction", "image_prompt_hint", "reply_hint"):
            if execution.get(key):
                directed_choice[key] = execution[key]
        prompt = self.build_choice_image_prompt(context, directed_choice)
        scene_update = {
            "scene_phase": "choice_transition",
            "location": execution.get("location") or state_json.get("location") or choice.get("label"),
            "background": execution.get("background") or directed_choice.get("image_prompt_hint"),
            "focus_summary": directed_choice.get("scene_instruction") or directed_choice.get("label"),
            "next_topic": directed_choice.get("reply_hint") or "react to the selected scene",
            "transition_occurred": True,
            "character_reaction_hint": directed_choice.get("reply_hint") or "",
            "image_focus": prompt,
            "selected_choice": directed_choice,
            "choice_execution": execution,
        }
        state_json["input_intent"] = {
            "intent": "visual_request",
            "reason": "scene choice selected by user",
            "should_generate_image": True,
        }
        state_json["scene_progression"] = scene_update
        state_json["directed_scene"] = scene_update
        state_json["visual_prompt_text"] = prompt
        self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "narration_note": scene_update["focus_summary"],
                "visual_prompt_text": prompt,
            },
        )

        user_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "narration",
                "speaker_name": "選択",
                "message_text": directed_choice.get("label") or "場面を選択",
                "message_role": "choice",
                "state_snapshot_json": {"scene_choice": directed_choice, "choice_execution": execution},
            },
        )
        generated_image = self._media_service.generate_image(
            session_id,
            {
                "image_type": "directed_scene",
                "prompt_text": prompt,
                "use_existing_prompt": True,
                "size": payload.get("size") or UserSettingService.DEFAULTS.get("default_size", "1024x1024"),
                "quality": payload.get("quality") or "low",
            },
        )
        updated_context = self._context_provider(session_id)
        reply = text_support.generate_narration_reaction(
            self._text_ai_client,
            updated_context,
            directed_choice.get("label") or "",
            scene_update,
        )
        assistant_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": reply["speaker_name"],
                "message_text": reply["message_text"],
                "message_role": "assistant",
                "state_snapshot_json": {
                    "scene_choice": choice,
                    "directed_choice": directed_choice,
                    "choice_execution": execution,
                    "directed_scene": scene_update,
                },
            },
        )
        updated_context = self._context_provider(session_id)
        self.update_line_visual_note(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.update_session_memory(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.update_conversation_evaluation(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        self.clear_scene_choices(session_id)
        updated_context = self._context_provider(session_id)
        return {
            "selected_choice": choice,
            "generated_image": generated_image,
            "messages": [self._serialize_message(user_message), self._serialize_message(assistant_message)],
            "context": updated_context,
        }
