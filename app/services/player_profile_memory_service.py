from __future__ import annotations

from datetime import datetime

from ..extensions import db
from ..models.player_profile_memory import PlayerProfileMemory
from ..utils import json_util


def _append_note(existing: str | None, note: str | None, *, limit: int = 1600) -> str:
    note = str(note or "").strip()
    if not note:
        return str(existing or "").strip()[:limit]
    existing = str(existing or "").strip()
    if note in existing:
        return existing[:limit]
    merged = "\n".join(item for item in [existing, f"- {note[:220]}"] if item)
    return merged[-limit:]


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(marker in text or marker.lower() in lowered for marker in markers)


class PlayerProfileMemoryService:
    """Shared long-term profile used by all characters for one player."""

    def get_memory(self, user_id: int):
        if not user_id:
            return None
        return PlayerProfileMemory.query.filter_by(user_id=user_id).first()

    def get_or_create_memory(self, user_id: int):
        row = self.get_memory(user_id)
        if row:
            return row
        row = PlayerProfileMemory(user_id=user_id, memory_enabled=True)
        db.session.add(row)
        db.session.commit()
        return row

    def serialize_memory(self, row) -> dict:
        if not row:
            return {}
        profile_json = {}
        if row.profile_json:
            try:
                profile_json = json_util.loads(row.profile_json) or {}
            except Exception:
                profile_json = {}
        return {
            "interest_notes": row.interest_notes or "",
            "dislike_notes": row.dislike_notes or "",
            "conversation_style_notes": row.conversation_style_notes or "",
            "humor_notes": row.humor_notes or "",
            "romance_notes": row.romance_notes or "",
            "goal_notes": row.goal_notes or "",
            "frustration_notes": row.frustration_notes or "",
            "recent_player_notes": row.recent_player_notes or "",
            "profile_json": profile_json,
            "last_interaction_at": row.last_interaction_at.isoformat() if row.last_interaction_at else None,
            "memory_enabled": bool(row.memory_enabled),
        }

    def build_prompt_block(self, user_id: int) -> str:
        row = self.get_memory(user_id)
        if not row or row.memory_enabled is False:
            return ""
        data = self.serialize_memory(row)
        if not any(str(data.get(key) or "").strip() for key in data if key not in {"memory_enabled", "last_interaction_at"}):
            return ""
        lines = [
            "全キャラクター共通のプレイヤープロフィール:",
            f"興味: {data['interest_notes'] or '(なし)'}",
            f"嫌いなもの/避けたい話題: {data['dislike_notes'] or '(なし)'}",
            f"好みの会話スタイル: {data['conversation_style_notes'] or '(なし)'}",
            f"ユーモアの好み: {data['humor_notes'] or '(なし)'}",
            f"恋愛上の境界線と好み: {data['romance_notes'] or '(なし)'}",
            f"現在の目標/関心: {data['goal_notes'] or '(なし)'}",
            f"繰り返し出る不満: {data['frustration_notes'] or '(なし)'}",
            f"最近のプレイヤーサイン: {data['recent_player_notes'] or '(なし)'}",
            "背景理解として使ってください。話題選び、説明の明瞭さ、ユーモア、会話のテンポ、恋愛的な距離感をプレイヤーに合わせてください。",
            "プロフィールを使っていることを宣言しないでください。現在のプレイヤー発言と矛盾する場合、古いメモ1つに過剰適応しないでください。",
        ]
        return "\n".join(lines)

    def update_from_user_message(self, *, user_id: int, user_text: str | None):
        text = str(user_text or "").strip()
        if not user_id or not text:
            return None
        row = self.get_or_create_memory(user_id)
        if row.memory_enabled is False:
            return row

        row.recent_player_notes = _append_note(row.recent_player_notes, text[:220], limit=2200)

        if _contains_any(text, ("好き", "すき", "興味", "関心", "ハマ", "面白", "楽しい", "推し", "like", "love", "interest", "fun")):
            row.interest_notes = _append_note(row.interest_notes, text)
        if _contains_any(text, ("嫌い", "苦手", "しんどい", "つまらない", "面白くない", "避け", "やめて", "dislike", "hate", "boring")):
            row.dislike_notes = _append_note(row.dislike_notes, text)
        if _contains_any(text, ("会話", "テンポ", "目的", "何の話", "わからない", "説明", "合わせ", "chat", "conversation", "pace")):
            row.conversation_style_notes = _append_note(row.conversation_style_notes, text)
        if _contains_any(text, ("笑", "ギャグ", "冗談", "ボケ", "ツッコミ", "おもろ", "funny", "joke", "humor", "comedy")):
            row.humor_notes = _append_note(row.humor_notes, text)
        if _contains_any(text, ("恋", "恋愛", "好きにな", "ドキドキ", "距離感", "好感", "romance", "romantic")):
            row.romance_notes = _append_note(row.romance_notes, text)
        if _contains_any(text, ("したい", "欲しい", "ほしい", "目的", "ゴール", "実装", "改良", "goal", "want", "need")):
            row.goal_notes = _append_note(row.goal_notes, text)
        if _contains_any(text, ("困", "悩", "問題", "原因", "ダメ", "きつい", "しんどい", "frustrat", "problem")):
            row.frustration_notes = _append_note(row.frustration_notes, text)

        profile = {
            "updated_from": "live_chat_user_message",
            "last_user_text": text[:500],
            "last_updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        row.profile_json = json_util.dumps(profile)
        row.last_interaction_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row

    def update_from_final_summary(
        self,
        *,
        user_id: int,
        interest_notes: str | None = None,
        dislike_notes: str | None = None,
        conversation_style_notes: str | None = None,
        humor_notes: str | None = None,
        romance_notes: str | None = None,
        goal_notes: str | None = None,
        frustration_notes: str | None = None,
        recent_player_notes: str | None = None,
        profile_json: dict | None = None,
    ):
        if not user_id:
            return None
        row = self.get_or_create_memory(user_id)
        if row.memory_enabled is False:
            return row
        fields = {
            "interest_notes": interest_notes,
            "dislike_notes": dislike_notes,
            "conversation_style_notes": conversation_style_notes,
            "humor_notes": humor_notes,
            "romance_notes": romance_notes,
            "goal_notes": goal_notes,
            "frustration_notes": frustration_notes,
            "recent_player_notes": recent_player_notes,
        }
        limits = {
            "interest_notes": 1600,
            "dislike_notes": 1200,
            "conversation_style_notes": 1600,
            "humor_notes": 1200,
            "romance_notes": 1600,
            "goal_notes": 1200,
            "frustration_notes": 1200,
            "recent_player_notes": 800,
        }
        for field, value in fields.items():
            text = str(value or "").strip()
            if text:
                setattr(row, field, text[: limits[field]])
        if profile_json is not None:
            payload = dict(profile_json or {})
            payload["updated_from"] = "live_chat_session_finalization"
            payload["last_updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            row.profile_json = json_util.dumps(payload)
        row.last_interaction_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row
