from __future__ import annotations

from ..clients.text_ai_client import TextAIClient
from . import learning_live_chat_prompt_support as learning_prompt
from .chat_message_service import ChatMessageService
from .chat_session_service import ChatSessionService
from .session_state_service import SessionStateService


class LearningLiveChatConversationService:
    """Learning-mode conversation engine, kept separate from romance flow."""

    def __init__(
        self,
        *,
        chat_session_service: ChatSessionService,
        chat_message_service: ChatMessageService,
        session_state_service: SessionStateService,
        text_ai_client: TextAIClient,
        context_provider,
        serialize_message,
        serialize_state,
        media_service=None,
    ):
        self._chat_session_service = chat_session_service
        self._chat_message_service = chat_message_service
        self._session_state_service = session_state_service
        self._text_ai_client = text_ai_client
        self._media_service = media_service
        self._context_provider = context_provider
        self._serialize_message = serialize_message
        self._serialize_state = serialize_state

    def _load_json(self, value):
        try:
            from ..utils import json_util

            parsed = json_util.loads(value) if isinstance(value, str) else value
        except Exception:
            parsed = {}
        return parsed if isinstance(parsed, dict) else {}

    def _build_learning_state(self, reply: dict) -> dict:
        return {
            "lesson_stage": reply.get("lesson_stage") or "",
            "board_items": reply.get("board_items") or [],
            "check_question": reply.get("check_question") or "",
            "next_teaching_action": reply.get("next_teaching_action") or "",
            "lesson_points": reply.get("lesson_points") or [],
            "current_point_index": reply.get("current_point_index") or 0,
            "teaching_aid_type": reply.get("teaching_aid_type") or "none",
            "teaching_aid_prompt": reply.get("teaching_aid_prompt") or "",
            "teaching_aid_choices": reply.get("teaching_aid_choices") or [],
        }

    def _speaker_name(self, context: dict | None = None) -> str:
        characters = (context or {}).get("characters") or []
        if characters:
            name = str((characters[0] or {}).get("name") or "").strip()
            if name:
                return name
        return "先生"

    def _followup_choices(self) -> dict:
        return {
            "choices": [
                {
                    "id": "learning_next",
                    "label": "次の説明へ",
                    "choice_type": "learning_next",
                    "reply_hint": "次のポイントへ進んで説明する。",
                },
                {
                    "id": "learning_check",
                    "label": "理解チェック",
                    "choice_type": "learning_check",
                    "reply_hint": "理解確認の短い問題を出す。",
                },
            ],
            "source": "learning_live_chat_followup",
            "allow_free_text": True,
        }

    def _fallback_teaching_aid_message(self, aid_type: str, learning_state: dict) -> str:
        board_items = [str(item).strip() for item in (learning_state.get("board_items") or []) if str(item).strip()]
        if board_items:
            return "この資料では「" + "、".join(board_items[:4]) + "」を中心に見れば大丈夫。ここを手がかりに、次の説明へ進もう。"
        return "この資料を手がかりにすると、次の説明が追いやすくなるよ。気になるところがあれば、そのまま聞いて。"

    def _teaching_aid_message(self, aid_type: str, learning_state: dict, context: dict | None = None) -> str:
        context = context or {}
        speaker_name = self._speaker_name(context)
        characters = context.get("characters") or []
        character = characters[0] if characters else {}
        board_items = [
            str(item).strip()
            for item in (learning_state.get("board_items") or [])
            if str(item).strip()
        ][:6]
        lesson_points = [
            str(item).strip()
            for item in (learning_state.get("lesson_points") or [])
            if str(item).strip()
        ][:8]
        recent_lines = []
        for message in (context.get("messages") or [])[-8:]:
            speaker = message.get("speaker_name") or message.get("sender_type") or ""
            text = str(message.get("message_text") or "").strip()
            if text:
                recent_lines.append(f"- {speaker}: {text[:220]}")
        prompt = "\n".join(
            [
                "学習モードのチャットで、教材画像を表示した直後にキャラクターが話す短い一言を作ってください。",
                "日本語で返してください。返答本文だけを書いてください。JSONや引用符は不要です。",
                "固定文のように「板書を更新したよ」だけで終わらせないでください。",
                "画像そのものをどう作ったかではなく、学習者がどこを見ればよいか、次の説明へどうつながるかを自然に話してください。",
                "1から3文、80から180字程度。キャラクターの口調を少し反映してください。",
                "吹き出し、画像生成、プロンプト、UI、ボタンという言葉は使わないでください。",
                f"話すキャラクター: {speaker_name}",
                f"性格: {character.get('personality') or ''}",
                f"口調: {character.get('speech_style') or ''}",
                f"教材タイプ: {aid_type}",
                f"教材の目的: {learning_state.get('teaching_aid_prompt') or ''}",
                "板書要点: " + "、".join(board_items),
                "授業ポイント: " + "、".join(lesson_points),
                "最近の会話:",
                *(recent_lines or ["- なし"]),
            ]
        )
        try:
            result = self._text_ai_client.generate_text(prompt, temperature=0.65, max_tokens=320)
            text = str((result or {}).get("text") or "").strip()
            if text:
                return text[:500]
        except Exception:
            pass
        return self._fallback_teaching_aid_message(aid_type, learning_state)

    def _choice(self, choice_id: str, label: str, choice_type: str, reply_hint: str, image_prompt_hint: str | None = None):
        item = {
            "id": choice_id,
            "label": label,
            "choice_type": choice_type,
            "reply_hint": reply_hint,
        }
        if image_prompt_hint:
            item["image_prompt_hint"] = image_prompt_hint
        return item

    def _initial_choices(self, reply: dict) -> dict:
        preferred = str(reply.get("teaching_aid_type") or "").strip().lower()
        choices = []
        seen = set()

        def add(item):
            if item["id"] in seen:
                return
            seen.add(item["id"])
            choices.append(item)

        aid_id_by_type = {
            "board": "learning_board",
            "map": "learning_map",
            "timeline": "learning_timeline",
            "diagram": "learning_diagram",
            "experiment": "learning_experiment",
            "photo": "learning_photo",
        }
        for item in reply.get("teaching_aid_choices") or []:
            if not isinstance(item, dict):
                continue
            aid_type = str(item.get("type") or "").strip().lower()
            choice_id = aid_id_by_type.get(aid_type)
            if not choice_id:
                continue
            add(
                self._choice(
                    choice_id,
                    str(item.get("label") or "").strip() or aid_type,
                    choice_id,
                    str(item.get("reply_hint") or "").strip() or "教材を表示する。",
                    str(item.get("image_prompt_hint") or "").strip() or None,
                )
            )

        if not choices:
            choice_id = aid_id_by_type.get(preferred)
            if choice_id:
                add(self._choice(choice_id, preferred, choice_id, "教材を表示する。", reply.get("teaching_aid_prompt")))
        visual_choices = choices[:3]
        required_choices = [
            self._choice("learning_next", "次の説明へ", "learning_next", "次のポイントへ進んで説明する。"),
            self._choice("learning_check", "理解チェック", "learning_check", reply.get("check_question") or "理解確認の短い問題を出す。"),
        ]
        return {"choices": [*visual_choices, *required_choices], "source": "learning_live_chat", "allow_free_text": True}

    def _update_learning_state(self, session_id: int, reply: dict):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None))
        state_json["live_chat_genre"] = "learning"
        state_json["learning_director"] = self._build_learning_state(reply)
        state_json["scene_choices"] = self._initial_choices(reply)
        self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _return_to_character_board_image(self, session_id: int):
        if not self._media_service:
            return None
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None))
        learning_state = state_json.get("learning_director") or {}
        board_items = [
            str(item).strip()
            for item in (learning_state.get("board_items") or [])
            if str(item).strip()
        ][:6]
        learning_state["teaching_aid_type"] = "board"
        learning_state["teaching_aid_prompt"] = (
            "キャラクターが先生役として黒板の横に立ち、次の説明内容を板書で整理している授業シーン。"
            "黒板、キャラクター、読みやすい要点を中心にする。"
        )
        if board_items:
            learning_state["teaching_aid_prompt"] += " 板書する要点: " + "、".join(board_items)
        state_json["learning_director"] = learning_state
        self._session_state_service.upsert_state(session_id, {"state_json": state_json})
        return self._media_service.generate_image(
            session_id,
            {
                "image_type": "learning_board",
                "size": "1536x1024",
                "quality": "low",
            },
        )

    def post_message(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        message_text = str(payload.get("message_text") or "").strip()
        if not message_text:
            message_text = "今日のテーマを黒板で説明して"
        user_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": payload.get("sender_type") or "user",
                "speaker_name": payload.get("speaker_name") or session.player_name or "プレイヤー",
                "message_text": message_text,
                "message_role": "player",
                "state_snapshot_json": {"input_intent": {"intent": "learning_message"}},
            },
        )
        created = [self._serialize_message(user_message)]
        auto_reply = str(payload.get("auto_reply", "true")).lower() not in {"0", "false", "no", "off"}
        reply = {}
        if auto_reply:
            context = self._context_provider(session_id)
            prompt = learning_prompt.build_learning_reply_prompt(context, message_text)
            try:
                result = self._text_ai_client.generate_text(
                    prompt,
                    temperature=0.45,
                    max_tokens=2600,
                    response_format={"type": "json_object"},
                )
                reply = learning_prompt.normalize_learning_reply(context, result.get("text"), message_text)
            except Exception:
                reply = learning_prompt.fallback_learning_reply(context, message_text)
            forced_point_index = payload.get("_forced_learning_point_index")
            if forced_point_index is not None:
                try:
                    reply["current_point_index"] = max(0, int(forced_point_index))
                except (TypeError, ValueError):
                    pass
            forced_lesson_points = payload.get("_forced_lesson_points")
            if isinstance(forced_lesson_points, list) and forced_lesson_points:
                reply["lesson_points"] = [str(item).strip() for item in forced_lesson_points if str(item).strip()][:10]
            assistant_message = self._chat_message_service.create_message(
                session_id,
                {
                    "sender_type": "character",
                    "speaker_name": reply["speaker_name"],
                    "message_text": reply["message_text"],
                    "message_role": "assistant",
                    "state_snapshot_json": {"learning_reply": reply},
                },
            )
            created.append(self._serialize_message(assistant_message))
            self._update_learning_state(session_id, reply)
        updated_context = self._context_provider(session_id)
        state = self._session_state_service.get_state(session_id)
        return {
            "messages": created,
            "state": self._serialize_state(state),
            "session": updated_context["session"],
            "input_intent": {"intent": "learning_message", "should_generate_image": False},
            "player_intent": {"type": "message", "label": "学習テーマ"},
            "generated_image": None,
            "image_generation_error": None,
            "auto_image_candidate": False,
            "new_letter": None,
            "deferred_letter": False,
            "deferred_processing": False,
            "affinity_feedback": [],
            "reply_effect": None,
            "context": updated_context,
        }

    def execute_scene_choice(self, session_id: int, choice_id: str, payload: dict | None = None):
        payload = dict(payload or {})
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None))
        learning_state = state_json.get("learning_director") or {}
        choice_id = str(choice_id)
        if choice_id in {"learning_board", "learning_map", "learning_timeline", "learning_diagram", "learning_experiment", "learning_photo"}:
            scene_choices = state_json.get("scene_choices") or {}
            selected_choice = next(
                (
                    item
                    for item in (scene_choices.get("choices") or [])
                    if str(item.get("id") or "") == choice_id
                ),
                {},
            )
            generated_image = None
            aid_type = {
                "learning_board": "board",
                "learning_map": "map",
                "learning_timeline": "timeline",
                "learning_diagram": "diagram",
                "learning_experiment": "experiment",
                "learning_photo": "photo",
            }[choice_id]
            learning_state["teaching_aid_type"] = aid_type
            if aid_type == "board":
                prompt_hint = "黒板を主役にした学習用板書。要点が読みやすく整理されている。"
            elif aid_type == "map":
                prompt_hint = "学習用の地図。国や地域の位置関係がわかる。必要な地名を読みやすく表示する。"
            elif aid_type == "timeline":
                prompt_hint = "学習用の年表。時代の流れと主要な出来事が読みやすく並んでいる。"
            elif aid_type == "diagram":
                prompt_hint = "学習用の図解。仕組み、因果関係、構造が矢印とラベルでわかる。"
            elif aid_type == "photo":
                prompt_hint = "学習用の実景写真風資料。現地の地形、風景、空気感、自然環境がわかる。人物や架空キャラクターは出さない。"
            else:
                prompt_hint = "学習用の実験イメージ。実験器具、操作、観察される現象がわかる。安全で教育的な理科教材として描く。"
            if selected_choice.get("image_prompt_hint"):
                prompt_hint = f"{prompt_hint} {selected_choice['image_prompt_hint']}"
            elif selected_choice.get("reply_hint"):
                prompt_hint = f"{prompt_hint} {selected_choice['reply_hint']}"
            if learning_state.get("teaching_aid_prompt"):
                prompt_hint = f"{prompt_hint} {learning_state['teaching_aid_prompt']}"
            learning_state["teaching_aid_prompt"] = prompt_hint
            state_json["learning_director"] = learning_state
            self._session_state_service.upsert_state(session_id, {"state_json": state_json})
            if self._media_service:
                generated_image = self._media_service.generate_image(
                    session_id,
                    {
                        "image_type": f"learning_{aid_type}",
                        "skip_character_references": aid_type in {"map", "timeline", "diagram", "experiment", "photo"},
                        "skip_outfit_prompt": aid_type in {"map", "timeline", "diagram", "experiment", "photo"},
                        "size": "1536x1024",
                        "quality": "low",
                    },
                )
            state_row = self._session_state_service.get_state(session_id)
            state_json = self._load_json(getattr(state_row, "state_json", None))
            state_json["live_chat_genre"] = "learning"
            state_json["learning_director"] = learning_state
            state_json["scene_choices"] = self._followup_choices()
            self._session_state_service.upsert_state(session_id, {"state_json": state_json})
            updated_context = self._context_provider(session_id)
            assistant_message = self._chat_message_service.create_message(
                session_id,
                {
                    "sender_type": "character",
                    "speaker_name": self._speaker_name(updated_context),
                    "message_text": self._teaching_aid_message(aid_type, learning_state, updated_context),
                    "message_role": "assistant",
                    "state_snapshot_json": {"learning_teaching_aid": {"type": aid_type}},
                },
            )
            updated_context = self._context_provider(session_id)
            return {
                "messages": [self._serialize_message(assistant_message)],
                "state": updated_context["state"],
                "session": updated_context["session"],
                "generated_image": generated_image,
                "image_generation_error": None,
                "auto_image_candidate": bool(generated_image),
                "context": updated_context,
            }
        if choice_id == "learning_check":
            message_text = learning_state.get("check_question") or "ここまでで、どこが一番ひっかかっていますか？"
        elif choice_id == "learning_next":
            points = learning_state.get("lesson_points") or []
            current_index = int(learning_state.get("current_point_index") or 0)
            next_index = min(current_index + 1, max(0, len(points) - 1))
            next_label = points[next_index] if points and next_index < len(points) else "次のポイント"
            learning_state["current_point_index"] = next_index
            state_json["learning_director"] = learning_state
            self._session_state_service.upsert_state(session_id, {"state_json": state_json})
            message_text = f"次は「{next_label}」について、内容そのものをわかりやすく説明して。"
        else:
            board_items = learning_state.get("board_items") or []
            if board_items:
                message_text = (
                    "ここで大事なのは、"
                    + "、".join(str(item) for item in board_items[:4])
                    + "の流れです。この順番で、内容そのものをもう少し詳しく説明して。"
                )
            else:
                message_text = "今のテーマについて、内容そのものをもう少し詳しく説明して。"
        result = self.post_message(
            session_id,
            {
                "message_text": message_text,
                "speaker_name": payload.get("speaker_name") or "プレイヤー",
                "_forced_learning_point_index": next_index if choice_id == "learning_next" else None,
                "_forced_lesson_points": points if choice_id == "learning_next" else None,
            },
        )
        if choice_id == "learning_next" and result:
            try:
                generated_image = self._return_to_character_board_image(session_id)
                if generated_image:
                    result["generated_image"] = generated_image
                    result["image_generation_error"] = None
                    result["auto_image_candidate"] = True
                    result["context"] = self._context_provider(session_id)
            except Exception as exc:
                result["generated_image"] = None
                result["image_generation_error"] = str(exc)
                result["auto_image_candidate"] = False
        return result

    def generate_player_proxy_message(self, session_id: int, payload: dict | None = None):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        return {
            "message_text": "このテーマを黒板で、要点と例を分けて説明して",
            "player_name": session.player_name or "プレイヤー",
            "purpose": "learning",
        }

    def post_idle_character_message(self, session_id: int):
        return self.post_message(session_id, {"message_text": "続きの要点を説明して", "speaker_name": "プレイヤー"})
