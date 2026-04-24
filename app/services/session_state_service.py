from __future__ import annotations

from ..clients.text_ai_client import TextAIClient
from ..utils import json_util
from ..repositories.session_state_repository import SessionStateRepository


class SessionStateService:
    def __init__(
        self,
        repository: SessionStateRepository | None = None,
        text_ai_client: TextAIClient | None = None,
    ):
        self._repo = repository or SessionStateRepository()
        self._text_ai_client = text_ai_client or TextAIClient()

    def get_state(self, session_id: int):
        return self._repo.get_by_session(session_id)

    def upsert_state(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        if "state_json" in payload and isinstance(payload["state_json"], (dict, list)):
            payload["state_json"] = json_util.dumps(payload["state_json"])
        return self._repo.upsert(session_id, payload)

    def _build_fallback_state(self, messages, character_ids: list[int]):
        last_message = messages[-1] if messages else None
        text = getattr(last_message, "message_text", None) or ""
        speaker_name = getattr(last_message, "speaker_name", None) or ""
        state = {
            "location": None,
            "background": None,
            "expression": "neutral",
            "pose": "conversation",
            "mood": "calm",
            "time_of_day": None,
            "camera": "medium shot",
            "focus_summary": f"{speaker_name}が話している場面" if speaker_name else "会話中の場面",
            "active_character_ids": character_ids,
            "latest_topic": text[:120] if text else None,
        }
        lowered = text.lower()
        if any(keyword in lowered for keyword in ("怒", "苛", "きつ", "強", "激")):
            state["expression"] = "angry"
            state["mood"] = "tense"
        elif any(keyword in lowered for keyword in ("笑", "楽", "嬉", "うれ")):
            state["expression"] = "smile"
            state["mood"] = "bright"
        elif any(keyword in lowered for keyword in ("悲", "泣", "つら", "寂")):
            state["expression"] = "sad"
            state["mood"] = "melancholic"
        return state

    def _build_state_prompt(self, *, session_title: str, characters: list[dict], messages: list[dict]):
        lines = [
            "以下のライブ会話ログから、表示中の一枚絵に必要な状態だけを JSON で抽出してください。",
            "返答は JSON object のみ。",
            "キーは location, background, expression, pose, mood, time_of_day, camera, focus_summary, active_character_names。",
            "",
            f"セッション名: {session_title}",
            "登場キャラクター:",
        ]
        for character in characters:
            lines.append(f"- {character.get('name')}: {character.get('role') or 'character'}")
        lines.append("")
        lines.append("会話ログ:")
        for item in messages[-12:]:
            lines.append(f"- {item.get('speaker_name') or item.get('sender_type')}: {item.get('message_text')}")
        return "\n".join(lines)

    def extract_state(self, *, session, messages, characters):
        character_ids = [character["id"] for character in characters]
        existing_row = self.get_state(session.id)
        existing_state_json = json_util.loads(existing_row.state_json) if existing_row and getattr(existing_row, "state_json", None) else {}
        try:
            prompt = self._build_state_prompt(
                session_title=getattr(session, "title", None) or "Live Chat",
                characters=characters,
                messages=messages,
            )
            result = self._text_ai_client.generate_text(
                prompt,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            parsed = self._text_ai_client._try_parse_json(result.get("text"))
            if not isinstance(parsed, dict):
                raise RuntimeError("state extraction response is invalid")
            active_names = parsed.get("active_character_names") or []
            if isinstance(active_names, list) and active_names:
                normalized_ids = [
                    character["id"]
                    for character in characters
                    if character["name"] in active_names
                ]
                if normalized_ids:
                    parsed["active_character_ids"] = normalized_ids
            parsed.setdefault("active_character_ids", character_ids)
            if isinstance(existing_state_json, dict):
                for key in ("scene_progression", "session_memory", "conversation_director", "relationship_state", "line_visual_note", "visual_state", "conversation_evaluation"):
                    if key in existing_state_json and key not in parsed:
                        parsed[key] = existing_state_json[key]
            return self.upsert_state(
                session.id,
                {
                    "state_json": parsed,
                    "narration_note": parsed.get("focus_summary"),
                },
            )
        except Exception:
            fallback_state = self._build_fallback_state(messages, character_ids)
            if isinstance(existing_state_json, dict):
                for key in ("scene_progression", "session_memory", "conversation_director", "relationship_state", "line_visual_note", "visual_state", "conversation_evaluation"):
                    if key in existing_state_json:
                        fallback_state[key] = existing_state_json[key]
            return self.upsert_state(
                session.id,
                {
                    "state_json": fallback_state,
                },
            )
