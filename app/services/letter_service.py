from __future__ import annotations

import os
from datetime import datetime

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..repositories.letter_repository import LetterRepository
from ..utils import json_util
from . import live_chat_image_support as image_support
from .asset_service import AssetService
from .character_service import CharacterService
from .chat_session_service import ChatSessionService
from .live_chat_room_service import LiveChatRoomService


class LetterService:
    def __init__(
        self,
        repository: LetterRepository | None = None,
        asset_service: AssetService | None = None,
        character_service: CharacterService | None = None,
        chat_session_service: ChatSessionService | None = None,
        live_chat_room_service: LiveChatRoomService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._repo = repository or LetterRepository()
        self._asset_service = asset_service or AssetService()
        self._character_service = character_service or CharacterService()
        self._chat_session_service = chat_session_service or ChatSessionService()
        self._live_chat_room_service = live_chat_room_service or LiveChatRoomService()
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

    def _serialize_asset(self, asset):
        if not asset:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
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
        return_url = (
            f"/projects/{letter.project_id}/live-chat/{letter.session_id}"
            if letter.session_id
            else f"/projects/{letter.project_id}/live-chat"
        )
        return {
            "id": letter.id,
            "project_id": letter.project_id,
            "room_id": letter.room_id,
            "session_id": letter.session_id,
            "recipient_user_id": letter.recipient_user_id,
            "sender_character_id": letter.sender_character_id,
            "sender_character": self._serialize_character(sender),
            "subject": letter.subject,
            "body": letter.body,
            "summary": letter.summary,
            "image_asset": self._serialize_asset(image_asset),
            "status": letter.status,
            "trigger_type": letter.trigger_type,
            "trigger_reason": letter.trigger_reason,
            "generation_state": self._load_json(letter.generation_state_json) or {},
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

    def generate_for_context(self, session, context: dict, *, trigger_type: str = "conversation"):
        if not session or not getattr(session, "owner_user_id", None):
            return None
        character = self._resolve_sender_character(context)
        if not character:
            return None
        messages = context.get("messages") or []
        if len(messages) < 6:
            return None
        room_id = getattr(session, "room_id", None)
        recent = self._repo.list_recent_for_guard(
            recipient_user_id=session.owner_user_id,
            sender_character_id=character["id"],
            room_id=room_id,
            hours=6,
        )
        if recent:
            return None

        decision = self._decide_should_send_letter(context, character, trigger_type)
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
                "subject": str(content.get("subject") or "あなたへ").strip()[:255],
                "body": str(content.get("body") or "").strip(),
                "summary": str(content.get("summary") or decision.get("reason") or "").strip() or None,
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
        state_json = ((context.get("state") or {}).get("state_json") or {})
        evaluation = state_json.get("conversation_evaluation") or {}
        room = context.get("room") or {}
        prompt = f"""
あなたは恋愛ノベル系ライブチャットの演出AIです。
会話ログを読み、今このユーザーにキャラクターから「メール」を届けるべきか判定してください。
頻繁に出しすぎず、プレイヤーが感情的に少し報われる、余韻がある、関係が進んだ、贈り物や印象的なやり取りがあった、という時だけ true にしてください。

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
現在の評価: {json_util.dumps(evaluation)}
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
  "image_direction": "添付画像の具体的な情景"
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
            "プレイヤー本人は画面に出さない。キャラクターがメールを書いた後の余韻が伝わる、"
            "感情的で映える一枚。"
            f"キャラクター: {character.get('name')}。"
            f"外見: {character.get('appearance_summary') or ''}。"
            f"画風: {character.get('art_style') or ''}。"
            f"情景: {direction}"
        )
        reference_paths = []
        reference_asset_ids = []
        base_asset = character.get("base_asset") or {}
        base_path = base_asset.get("file_path")
        if base_path and os.path.exists(base_path):
            reference_paths.append(base_path)
            reference_asset_ids.append(base_asset.get("id"))
        result = self._image_ai_client.generate_image(
            prompt,
            size="1536x1024",
            quality="low",
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
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_asset_ids,
                    }
                ),
            },
        )
        return asset.id
