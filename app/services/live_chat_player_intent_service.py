from __future__ import annotations


class LiveChatPlayerIntentService:
    """Normalize structured player input before it reaches conversation logic."""

    _ALLOWED_TYPES = {"message", "action", "emotion"}

    def normalize(self, payload: dict | None, raw_message_text: str = "", context: dict | None = None) -> dict:
        payload = dict(payload or {})
        raw_intent = payload.get("player_intent")
        if not isinstance(raw_intent, dict):
            raw_intent = {}
        intent_type = str(raw_intent.get("type") or payload.get("intent_type") or "message").strip().lower()
        if intent_type not in self._ALLOWED_TYPES:
            intent_type = "message"
        label = str(raw_intent.get("label") or "").strip()
        intent_id = str(raw_intent.get("id") or "").strip()
        if intent_type == "message":
            label = label or "メッセージ"
            intent_id = intent_id or "free_text"
        target_character_id = self._normalize_int(raw_intent.get("target_character_id") or payload.get("target_character_id"))
        intensity = self._normalize_int(raw_intent.get("intensity"), default=None)
        return {
            "type": intent_type,
            "id": intent_id,
            "label": label,
            "description": str(raw_intent.get("description") or "").strip(),
            "tone": str(raw_intent.get("tone") or "").strip(),
            "target_character_id": target_character_id,
            "intensity": intensity,
            "raw_message_text": str(raw_message_text or "").strip(),
        }

    def render_message_text(self, intent: dict, raw_message_text: str = "") -> str:
        raw = str(raw_message_text or intent.get("raw_message_text") or "").strip()
        intent_type = str(intent.get("type") or "message").strip().lower()
        if intent_type == "action":
            label = str(intent.get("label") or intent.get("description") or "行動する").strip()
            return raw or f"{label}。"
        if intent_type == "emotion":
            label = str(intent.get("label") or "今の気持ち").strip()
            return raw or f"{label}気持ちを伝える。"
        return raw

    def prompt_text(self, intent: dict, message_text: str) -> str:
        intent_type = str(intent.get("type") or "message").strip().lower()
        if intent_type == "action":
            details = self._details(intent)
            return f"[Player action] {message_text}{details}"
        if intent_type == "emotion":
            details = self._details(intent)
            return f"[Player emotion] {message_text}{details}"
        return message_text

    def _details(self, intent: dict) -> str:
        parts = []
        if intent.get("label"):
            parts.append(f"label={intent['label']}")
        if intent.get("description"):
            parts.append(f"description={intent['description']}")
        if intent.get("tone"):
            parts.append(f"tone={intent['tone']}")
        if intent.get("intensity") is not None:
            parts.append(f"intensity={intent['intensity']}")
        return f" ({', '.join(parts)})" if parts else ""

    def _normalize_int(self, value, default=0):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed
