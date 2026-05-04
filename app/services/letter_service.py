from __future__ import annotations

import os
import threading
from datetime import datetime

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..extensions import db
from ..repositories.letter_repository import LetterRepository
from ..utils import json_util
from . import live_chat_image_support as image_support
from .asset_service import AssetService
from .character_service import CharacterService
from .chat_session_service import ChatSessionService
from .live_chat_room_service import LiveChatRoomService
from .user_setting_service import UserSettingService


class LetterService:
    def __init__(
        self,
        repository: LetterRepository | None = None,
        asset_service: AssetService | None = None,
        character_service: CharacterService | None = None,
        chat_session_service: ChatSessionService | None = None,
        live_chat_room_service: LiveChatRoomService | None = None,
        user_setting_service: UserSettingService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._repo = repository or LetterRepository()
        self._asset_service = asset_service or AssetService()
        self._character_service = character_service or CharacterService()
        self._chat_session_service = chat_session_service or ChatSessionService()
        self._live_chat_room_service = live_chat_room_service or LiveChatRoomService()
        self._user_setting_service = user_setting_service or UserSettingService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()

    def _load_json(self, value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return json_util.loads(value)
        except Exception:
            return None

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

    def _normalize_text(self, value):
        return (
            str(value or "")
            .replace("\\r\\n", "\n")
            .replace("\\n", "\n")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
            .strip()
        )

    def _serialize_asset(self, asset):
        if not asset:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "file_path": asset.file_path,
            "mime_type": asset.mime_type,
            "media_url": self._build_media_url(asset.file_path),
        }

    def _serialize_character(self, character):
        if not character:
            return None
        thumbnail = self._asset_service.get_asset(character.thumbnail_asset_id) if character.thumbnail_asset_id else None
        base_asset = self._asset_service.get_asset(character.base_asset_id) if character.base_asset_id else None
        return {
            "id": character.id,
            "name": character.name,
            "nickname": getattr(character, "nickname", None),
            "thumbnail_asset": self._serialize_asset(thumbnail),
            "base_asset": self._serialize_asset(base_asset),
        }

    def serialize_letter(self, letter):
        if not letter:
            return None
        sender = self._character_service.get_character(letter.sender_character_id)
        image_asset = self._asset_service.get_asset(letter.image_asset_id) if letter.image_asset_id else None
        generation_state = self._load_json(letter.generation_state_json) or {}
        return_url = (
            generation_state.get("return_url")
            or (
                f"/projects/{letter.project_id}/live-chat/{letter.session_id}"
                if letter.session_id
                else f"/projects/{letter.project_id}/live-chat"
            )
        )
        return {
            "id": letter.id,
            "project_id": letter.project_id,
            "room_id": letter.room_id,
            "session_id": letter.session_id,
            "recipient_user_id": letter.recipient_user_id,
            "sender_character_id": letter.sender_character_id,
            "sender_character": self._serialize_character(sender),
            "subject": self._normalize_text(letter.subject),
            "body": self._normalize_text(letter.body),
            "summary": self._normalize_text(letter.summary),
            "image_asset": self._serialize_asset(image_asset),
            "status": letter.status,
            "trigger_type": letter.trigger_type,
            "trigger_reason": letter.trigger_reason,
            "generation_state": generation_state,
            "return_url": return_url,
            "read_at": letter.read_at.isoformat() if letter.read_at else None,
            "created_at": letter.created_at.isoformat() if letter.created_at else None,
            "updated_at": letter.updated_at.isoformat() if letter.updated_at else None,
        }

    def list_for_user(self, user_id: int):
        return [self.serialize_letter(item) for item in self._repo.list_for_user(user_id)]

    def unread_count(self, user_id: int):
        return self._repo.count_unread_for_user(user_id)

    def get_for_user(self, letter_id: int, user_id: int):
        letter = self._repo.get(letter_id)
        if not letter or letter.recipient_user_id != user_id or letter.deleted_at is not None:
            return None
        return self.serialize_letter(letter)

    def mark_read_for_user(self, letter_id: int, user_id: int):
        letter = self._repo.get(letter_id)
        if not letter or letter.recipient_user_id != user_id or letter.deleted_at is not None:
            return None
        return self.serialize_letter(self._repo.mark_read(letter_id))

    def archive_for_user(self, letter_id: int, user_id: int):
        letter = self._repo.get(letter_id)
        if not letter or letter.recipient_user_id != user_id or letter.deleted_at is not None:
            return None
        return self.serialize_letter(self._repo.archive(letter_id))

    def try_generate_for_context(self, session, context: dict, *, trigger_type: str = "conversation"):
        try:
            return self.generate_for_context(session, context, trigger_type=trigger_type)
        except Exception:
            try:
                current_app.logger.exception("letter generation failed")
            except RuntimeError:
                pass
            return None

    def schedule_generate_for_context(self, session_id: int, context: dict, *, trigger_type: str = "conversation") -> bool:
        if trigger_type in {"conversation", "scene_transition", "gift"}:
            return False
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            session = self._chat_session_service.get_session(session_id)
            self.try_generate_for_context(session, context, trigger_type=trigger_type)
            return False

        def worker():
            with app.app_context():
                try:
                    session = self._chat_session_service.get_session(session_id)
                    self.try_generate_for_context(session, context, trigger_type=trigger_type)
                except Exception:
                    app.logger.exception("deferred letter generation failed")
                finally:
                    db.session.remove()

        threading.Thread(target=worker, name=f"letter-generate-{session_id}", daemon=True).start()
        return True

    def schedule_generate_affinity_threshold_letter(
        self,
        session_id: int,
        context: dict,
        *,
        character_id: int,
        threshold: int,
    ) -> bool:
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            session = self._chat_session_service.get_session(session_id)
            self.try_generate_affinity_threshold_letter(
                session,
                context,
                character_id=character_id,
                threshold=threshold,
            )
            return False

        def worker():
            with app.app_context():
                try:
                    session = self._chat_session_service.get_session(session_id)
                    self.try_generate_affinity_threshold_letter(
                        session,
                        context,
                        character_id=character_id,
                        threshold=threshold,
                    )
                except Exception:
                    app.logger.exception("affinity threshold letter generation failed")
                finally:
                    db.session.remove()

        threading.Thread(
            target=worker,
            name=f"affinity-letter-{session_id}-{character_id}-{threshold}",
            daemon=True,
        ).start()
        return True

    def try_generate_affinity_threshold_letter(
        self,
        session,
        context: dict,
        *,
        character_id: int,
        threshold: int,
    ):
        try:
            return self.generate_affinity_threshold_letter(
                session,
                context,
                character_id=character_id,
                threshold=threshold,
            )
        except Exception:
            try:
                current_app.logger.exception("affinity threshold letter generation failed")
            except RuntimeError:
                pass
            return None

    def generate_for_context(self, session, context: dict, *, trigger_type: str = "conversation"):
        if not session or not getattr(session, "owner_user_id", None):
            return None
        character = self._resolve_sender_character(context)
        if not character:
            return None
        self._apply_context_letter_references(context, character)
        messages = context.get("messages") or []
        if len(messages) < 6:
            return None
        room_id = getattr(session, "room_id", None)
        cooldown_minutes = int(current_app.config.get("LETTER_COOLDOWN_MINUTES", 30))
        recent = self._repo.list_recent_for_guard(
            recipient_user_id=session.owner_user_id,
            sender_character_id=character["id"],
            room_id=room_id,
            minutes=cooldown_minutes,
        )
        if recent:
            return None

        decision = self._decide_should_send_letter(context, character, trigger_type)
        if not decision.get("should_send_letter"):
            decision = self._fallback_letter_decision(context, character, trigger_type)
        if not decision.get("should_send_letter"):
            return None
        content = self._generate_letter_content(context, character, decision)
        if not content.get("body"):
            return None
        image_asset_id = self._generate_letter_image_asset(session, context, character, content)
        letter = self._repo.create(
            {
                "project_id": session.project_id,
                "room_id": room_id,
                "session_id": session.id,
                "recipient_user_id": session.owner_user_id,
                "sender_character_id": character["id"],
                "subject": self._normalize_text(content.get("subject") or "あなたへ")[:255],
                "body": self._normalize_text(content.get("body")),
                "summary": self._normalize_text(content.get("summary") or decision.get("reason")) or None,
                "image_asset_id": image_asset_id,
                "status": "unread",
                "trigger_type": trigger_type,
                "trigger_reason": str(decision.get("reason") or "").strip() or None,
                "generation_state_json": json_util.dumps(
                    {
                        "decision": decision,
                        "content": content,
                        "generated_at": datetime.utcnow().isoformat(),
                    }
                ),
            }
        )
        return self.serialize_letter(letter)

    def _apply_context_letter_references(self, context: dict, character: dict) -> None:
        if context.get("letter_reference_asset_ids"):
            return
        reference_asset_id = self._room_outfit_asset_id(context)
        if not reference_asset_id:
            reference_asset_id = self._selected_costume_asset_id(context)
        if not reference_asset_id:
            reference_asset_id = ((character or {}).get("base_asset") or {}).get("id") or (character or {}).get("base_asset_id")
        if reference_asset_id:
            context["letter_reference_asset_ids"] = [reference_asset_id]

    def _room_outfit_asset_id(self, context: dict):
        room = context.get("room") if isinstance(context.get("room"), dict) else {}
        outfit = room.get("default_outfit") if isinstance(room.get("default_outfit"), dict) else {}
        asset = outfit.get("asset") if isinstance(outfit.get("asset"), dict) else {}
        return asset.get("id") or outfit.get("asset_id")

    def _selected_costume_asset_id(self, context: dict):
        costume = context.get("selected_costume") if isinstance(context.get("selected_costume"), dict) else {}
        asset = costume.get("asset") if isinstance(costume.get("asset"), dict) else {}
        return asset.get("id") or costume.get("asset_id")

    def generate_for_story_context(self, story_session, context: dict, *, trigger_type: str = "story_clear"):
        if not story_session or not getattr(story_session, "owner_user_id", None):
            return None
        character = self._resolve_sender_character(context)
        if not character:
            return None
        messages = context.get("messages") or context.get("recent_messages") or []
        if len(messages) < 2:
            return None
        existing = self._repo.find_story_clear_for_session(
            story_session_id=story_session.id,
            recipient_user_id=story_session.owner_user_id,
            sender_character_id=character["id"],
            project_id=story_session.project_id,
            trigger_type=trigger_type,
        )
        if existing:
            return self.serialize_letter(existing)
        decision = {
            "should_send_letter": True,
            "reason": "ストーリーをクリアしたため、一区切りの余韻としてキャラクターからメールを送る。",
            "emotional_hook": "一緒に最後までたどり着いた相手へ、会いたさと感謝を残す",
            "image_direction": f"{character.get('name') or 'キャラクター'}がストーリー後の余韻の中でこちらを思い出し、また会いたいと感じさせる表情を見せる場面。",
        }
        content = self._generate_letter_content(context, character, decision)
        if not content.get("body"):
            return None
        image_asset_id = self._generate_letter_image_asset(story_session, context, character, content)
        return_url = f"/projects/{story_session.project_id}/story-sessions/{story_session.id}"
        letter = self._repo.create(
            {
                "project_id": story_session.project_id,
                "room_id": None,
                "session_id": None,
                "recipient_user_id": story_session.owner_user_id,
                "sender_character_id": character["id"],
                "subject": self._normalize_text(content.get("subject") or "また会いたい")[:255],
                "body": self._normalize_text(content.get("body")),
                "summary": self._normalize_text(content.get("summary") or decision.get("reason")) or None,
                "image_asset_id": image_asset_id,
                "status": "unread",
                "trigger_type": trigger_type,
                "trigger_reason": decision["reason"],
                "generation_state_json": json_util.dumps(
                    {
                        "decision": decision,
                        "content": content,
                        "story_session_id": story_session.id,
                        "return_url": return_url,
                        "generated_at": datetime.utcnow().isoformat(),
                    }
                ),
            }
        )
        return self.serialize_letter(letter)

    def generate_affinity_threshold_letter(
        self,
        session,
        context: dict,
        *,
        character_id: int,
        threshold: int,
    ):
        if not session or not getattr(session, "owner_user_id", None):
            return None
        threshold = int(threshold)
        trigger_type = f"affinity_{threshold}"
        character = next(
            (item for item in (context.get("characters") or []) if int(item.get("id") or 0) == int(character_id)),
            None,
        )
        if not character:
            return None
        existing = self._repo.find_for_session_trigger(
            session_id=session.id,
            recipient_user_id=session.owner_user_id,
            sender_character_id=character_id,
            trigger_type=trigger_type,
        )
        if existing:
            return self.serialize_letter(existing)
        self._apply_context_letter_references(context, character)
        memory = (context.get("character_user_memories") or {}).get(str(character_id)) or {}
        tone_by_threshold = {
            60: "親密さがはっきり増え、また話したい気持ちを隠しきれない",
            80: "強い好意と独占欲に近い切なさが混じり、特別な相手だと伝わる",
            100: "心の底から愛していると告白する、情熱的で決定的な愛情",
        }
        decision = {
            "should_send_letter": True,
            "reason": f"セッション好感度が{threshold}に到達したため。",
            "emotional_hook": tone_by_threshold.get(threshold) or "関係が深まった節目",
            "image_direction": (
                f"{character.get('name') or 'キャラクター'}がプレイヤーへの気持ちを抑えきれず、"
                "こちらを見つめるドラマチックなイベントCG。文字や手紙そのものは描かない。"
            ),
            "affinity_threshold": threshold,
            "session_affinity": memory,
        }
        content = self._generate_letter_content(context, character, decision)
        if not content.get("body"):
            player_name = ((context.get("session") or {}).get("player_name") or "あなた").strip()
            content = {
                "subject": f"{player_name}へ",
                "body": (
                    f"{player_name}へ\n\n"
                    f"今日、あなたとの距離がまた少し変わった気がします。\n"
                    f"うまく言えないけれど、私にとってあなたはもう、ただの誰かではありません。\n\n"
                    f"{character.get('name') or ''}"
                ),
                "summary": f"好感度{threshold}到達メール",
                "image_direction": decision["image_direction"],
            }
        image_asset_id = self._generate_letter_image_asset(session, context, character, content)
        letter = self._repo.create(
            {
                "project_id": session.project_id,
                "room_id": getattr(session, "room_id", None),
                "session_id": session.id,
                "recipient_user_id": session.owner_user_id,
                "sender_character_id": character_id,
                "subject": self._normalize_text(content.get("subject") or f"好感度{threshold}到達")[:255],
                "body": self._normalize_text(content.get("body")),
                "summary": self._normalize_text(content.get("summary") or decision.get("reason")) or None,
                "image_asset_id": image_asset_id,
                "status": "unread",
                "trigger_type": trigger_type,
                "trigger_reason": decision["reason"],
                "generation_state_json": json_util.dumps(
                    {
                        "decision": decision,
                        "content": content,
                        "session_id": session.id,
                        "character_id": character_id,
                        "affinity_threshold": threshold,
                        "generated_at": datetime.utcnow().isoformat(),
                    }
                ),
            }
        )
        return self.serialize_letter(letter)

    def create_affinity_100_letter(self, session, context: dict, character_id: int, image_asset_id: int | None):
        if not session or not getattr(session, "owner_user_id", None):
            return None
        existing = self._repo.find_for_session_trigger(
            session_id=session.id,
            recipient_user_id=session.owner_user_id,
            sender_character_id=character_id,
            trigger_type="affinity_100",
        )
        if existing:
            return self.serialize_letter(existing)
        character = next(
            (item for item in (context.get("characters") or []) if int(item.get("id") or 0) == int(character_id)),
            None,
        )
        if not character:
            return None
        player_name = ((context.get("session") or {}).get("player_name") or "あなた").strip()
        name = character.get("name") or "キャラクター"
        content = {
            "subject": f"{player_name}へ",
            "body": (
                f"{player_name}へ\n\n"
                "もうごまかせないくらい、あなたのことが好きです。\n"
                "一緒に過ごした時間のひとつひとつが、私の中で特別になっていました。\n"
                "あなたの声を待ってしまうことも、近くにいたいと思ってしまうことも、"
                "今はもう全部、心の底からの本当の気持ちです。\n\n"
                "私はあなたを愛しています。\n"
                "この気持ちを、今日の記念の画像と一緒に受け取ってください。\n\n"
                f"{name}より"
            ),
            "summary": "好感度100達成の愛情メール",
        }
        letter = self._repo.create(
            {
                "project_id": session.project_id,
                "room_id": getattr(session, "room_id", None),
                "session_id": session.id,
                "recipient_user_id": session.owner_user_id,
                "sender_character_id": character_id,
                "subject": content["subject"][:255],
                "body": content["body"],
                "summary": content["summary"],
                "image_asset_id": image_asset_id,
                "status": "unread",
                "trigger_type": "affinity_100",
                "trigger_reason": "好感度100達成",
                "generation_state_json": json_util.dumps(
                    {
                        "content": content,
                        "session_id": session.id,
                        "character_id": character_id,
                        "generated_at": datetime.utcnow().isoformat(),
                    }
                ),
            }
        )
        return self.serialize_letter(letter)

    def _fallback_letter_decision(self, context: dict, character: dict, trigger_type: str):
        messages = context.get("messages") or []
        if len(messages) < 12:
            return {"should_send_letter": False}
        if trigger_type == "scene_transition":
            return {
                "should_send_letter": True,
                "reason": "会話が一定以上続き、関係の変化や余韻をメールで返せる節目になっているため。",
                "emotional_hook": "会話の続きを期待させる余韻",
                "image_direction": f"{character.get('name') or 'キャラクター'}がこちらを思い出して、少し照れた柔らかい表情を見せる場面。紙の手紙や封筒は描かない",
                "fallback": True,
            }
        return {"should_send_letter": False}

    def _resolve_sender_character(self, context: dict):
        characters = context.get("characters") or []
        if not characters:
            return None
        state_json = ((context.get("state") or {}).get("state_json") or {})
        active_ids = state_json.get("active_character_ids") or []
        if active_ids:
            for character in characters:
                if character.get("id") in set(active_ids):
                    return character
        room = context.get("room") or {}
        room_character_id = room.get("character_id")
        if room_character_id:
            for character in characters:
                if character.get("id") == room_character_id:
                    return character
        return characters[0]

    def _conversation_excerpt(self, context: dict, limit: int = 16):
        lines = []
        for message in (context.get("messages") or [])[-limit:]:
            speaker = message.get("speaker_name") or message.get("sender_type") or "unknown"
            text = str(message.get("message_text") or "").strip()
            if text:
                lines.append(f"{speaker}: {text}")
        return "\n".join(lines)

    def _decide_should_send_letter(self, context: dict, character: dict, trigger_type: str):
        room = context.get("room") or {}
        memory = (context.get("character_user_memories") or {}).get(str(character.get("id") or "")) or {}
        prompt = f"""
あなたは恋愛ノベル系ライブチャットの演出AIです。
会話ログを読み、今このユーザーにキャラクターから「メール」を届けるべきか判定してください。
頻繁に出しすぎない前提で、プレイヤーが感情的に少し報われる、余韻がある、関係が進んだ、贈り物や印象的なやり取りがあった、また会いたくなる引きが作れる、という兆候があれば積極的に true にしてください。

出力はJSONのみ:
{{
  "should_send_letter": true/false,
  "reason": "短い日本語",
  "emotional_hook": "メールで刺すべき感情",
  "image_direction": "メールに添えるイベント画像の方向性"
}}

キャラクター: {character.get("name")}
あだ名: {character.get("nickname") or ""}
キャラクターの性格: {character.get("personality") or ""}
話し方: {character.get("speech_style") or ""}
ルームの目的: {room.get("conversation_objective") or ""}
現在のキャラ別好感度: {json_util.dumps(memory)}
トリガー種別: {trigger_type}

会話ログ:
{self._conversation_excerpt(context)}
"""
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.35,
            response_format={"type": "json_object"},
            max_tokens=700,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        return parsed if isinstance(parsed, dict) else {}

    def _generate_letter_content(self, context: dict, character: dict, decision: dict):
        session = context.get("session") or {}
        room = context.get("room") or {}
        player_name = session.get("player_name") or "あなた"
        prompt = f"""
キャラクターからプレイヤーへ届く、短いメールを書いてください。
業務連絡のようなメールではなく、少し特別なDM/手紙のような文体にしてください。
会話ログの内容を踏まえ、プレイヤーが「また会いに行きたい」と感じるようにします。
ただし重すぎる告白にしないでください。キャラクターの口調・一人称・呼び方を優先してください。

出力はJSONのみ:
{{
  "subject": "件名",
  "body": "本文。改行を含めてよい。180〜420字程度",
  "summary": "一覧表示用の短い要約",
  "image_direction": "添付画像の具体的な情景。紙の手紙・封筒・スマホ・文字は描かず、受け取ったユーザーがキャラクターを可愛い、また会いたいと思う表情・仕草・距離感・雰囲気にする"
}}

宛先名: {player_name}
キャラクター名: {character.get("name")}
あだ名: {character.get("nickname") or ""}
一人称: {character.get("first_person") or ""}
相手の呼び方: {character.get("second_person") or ""}
性格: {character.get("personality") or ""}
話し方: {character.get("speech_style") or ""}
セリフサンプル: {character.get("speech_sample") or ""}
NGルール: {character.get("ng_rules") or ""}
ルームの目的: {room.get("conversation_objective") or ""}
メールを出す理由: {decision.get("reason") or ""}
刺す感情: {decision.get("emotional_hook") or ""}

会話ログ:
{self._conversation_excerpt(context)}
"""
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.75,
            response_format={"type": "json_object"},
            max_tokens=1100,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        return parsed if isinstance(parsed, dict) else {}

    def _generate_letter_image_asset(self, session, context: dict, character: dict, content: dict):
        direction = str(content.get("image_direction") or "").strip()
        if not direction:
            return None
        prompt = (
            "ノベルゲームのイベントCG。画像内には文字を一切入れない。セリフ、字幕、吹き出し、"
            "看板の読める文字、UI、ロゴ、透かし、擬音文字は入れない。"
            "プレイヤー本人は画面に出さない。"
            "紙の手紙、封筒、スマホ、画面、文字、文章、ペンを持つ描写は禁止。"
            "メールそのものを描くのではなく、メールを受け取ったユーザーが"
            "キャラクターを可愛い、また会いたいと思うような、表情・仕草・距離感・空気感で見せる。"
            "キャラクターがこちらを思い出している、または次に会う約束を感じさせる、"
            "感情的で映えるイベントCG。"
            "参照画像・基準画像がある場合は、それを現在のキャラクター基準画像として最優先で使う。"
            "同じ人物、同じ顔立ち、同じ髪型、同じ体型、同じ年齢感、同じ画風、同じ質感を維持する。"
            "参照画像が衣装画像の場合は、同じ衣装デザイン、配色、素材感、装飾を維持し、別衣装に変更しない。"
            "線の太さ、塗り、色味、光の質感、肌や髪のレンダリング、キャラクターデザインの密度を変えない。"
            "別作品の絵柄に寄せず、同じ作家・同じシリーズのイベントCGに見えるようにする。"
            f"キャラクター: {character.get('name')}。"
            f"外見: {character.get('appearance_summary') or ''}。"
            f"画風: {character.get('art_style') or ''}。"
            f"情景: {direction}"
        )
        reference_paths = []
        reference_asset_ids = []
        for asset_id in context.get("letter_reference_asset_ids") or []:
            if not asset_id:
                continue
            asset = self._asset_service.get_asset(asset_id)
            if asset and getattr(asset, "file_path", None) and os.path.exists(asset.file_path):
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)
                break
        base_asset = character.get("base_asset") or {}
        base_path = base_asset.get("file_path")
        if not reference_paths and base_path and os.path.exists(base_path):
            reference_paths.append(base_path)
            reference_asset_ids.append(base_asset.get("id"))
        if not reference_paths and base_asset.get("id"):
            asset = self._asset_service.get_asset(base_asset.get("id"))
            if asset and getattr(asset, "file_path", None) and os.path.exists(asset.file_path):
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)
        image_options = {}
        try:
            image_options = self._user_setting_service.apply_global_image_generation_settings(
                {"size": "1536x1024", "quality": current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium")},
            )
        except Exception:
            image_options = {
                "size": "1536x1024",
                "quality": current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            }
        result = self._image_ai_client.generate_image(
            prompt,
            size=image_options.get("size") or "1536x1024",
            quality=image_options.get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            model=image_options.get("model"),
            provider=image_options.get("provider"),
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            return None
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
                "asset_type": "letter_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "letter",
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "quality": result.get("quality") or image_options.get("quality"),
                        "size": image_options.get("size") or "1536x1024",
                        "aspect_ratio": result.get("aspect_ratio"),
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_asset_ids,
                    }
                ),
            },
        )
        return asset.id
