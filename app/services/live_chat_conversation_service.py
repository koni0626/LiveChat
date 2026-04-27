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
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

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
                "choices": choices_result["choices"][:2],
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
        updated_context = self._context_provider(session_id)
        self.update_conversation_evaluation(session_id, updated_context)
        updated_context = self._context_provider(session_id)
        state = self._extract_state_payload(session, updated_context)
        updated_context = self._context_provider(session_id)
        new_letter = self._letter_service.try_generate_for_context(
            session,
            updated_context,
            trigger_type="scene_transition",
        )
        return {
            "messages": [self._serialize_message(user_message), self._serialize_message(assistant_message)],
            "state": state,
            "session": updated_context["session"],
            "input_intent": intent,
            "generated_image": generated_image,
            "new_letter": new_letter,
        }

    def post_message(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        message_text = str(payload.get("message_text") or "").strip() or "話を進めて"
        initial_context = self._context_provider(session_id)
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
                "state_snapshot_json": {"input_intent": input_intent},
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
            state = self._extract_state_payload(session, updated_context)
            updated_context = self._context_provider(session_id)
            if assistant_message:
                self.update_scene_choices(session_id, updated_context, assistant_message)
                updated_context = self._context_provider(session_id)
            new_letter = self._letter_service.try_generate_for_context(
                session,
                updated_context,
                trigger_type="conversation",
            )
        return {
            "messages": created,
            "state": state,
            "session": updated_context["session"],
            "input_intent": input_intent,
            "generated_image": generated_image,
            "image_generation_error": image_generation_error,
            "auto_image_candidate": bool(auto_image_candidate),
            "new_letter": new_letter,
            "deferred_processing": deferred_processing,
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
                "size": payload.get("size") or "1536x1024",
                "quality": payload.get("quality") or "low",
            },
        )
        self.clear_scene_choices(session_id)
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
        return {
            "selected_choice": choice,
            "generated_image": generated_image,
            "messages": [self._serialize_message(user_message), self._serialize_message(assistant_message)],
            "context": updated_context,
        }
