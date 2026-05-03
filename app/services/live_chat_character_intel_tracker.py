from __future__ import annotations

from .character_intel_hint_service import CharacterIntelHintService


class LiveChatCharacterIntelTracker:
    """Tracks cross-character hints revealed or used during live chat."""

    def __init__(self, hint_service: CharacterIntelHintService | None = None):
        self._hint_service = hint_service or CharacterIntelHintService()

    def record_reveals(self, session, context: dict, character_text: str):
        if not session or not character_text:
            return
        text = str(character_text or "")
        for hint in ((context.get("character_intel") or {}).get("available_hints") or []):
            topic = str(hint.get("topic") or "").strip()
            target_name = str(hint.get("target_character_name") or "").strip()
            if not topic or topic not in text:
                continue
            if target_name and target_name not in text:
                continue
            self._hint_service.upsert_revealed_hint(
                user_id=int(session.owner_user_id),
                project_id=int(session.project_id),
                target_character_id=int(hint.get("target_character_id") or 0),
                source_character_id=int(hint.get("source_character_id") or 0),
                topic=topic,
                hint_text=str(hint.get("hint_text") or "").strip(),
                reveal_threshold=int(hint.get("reveal_threshold") or 40),
            )

    def mark_used(self, context: dict, user_text: str):
        if not user_text:
            return
        text = str(user_text or "")
        for hint in ((context.get("character_intel") or {}).get("learned_hints_for_active_targets") or []):
            if hint.get("status") == "used":
                continue
            topic = str(hint.get("topic") or "").strip()
            if topic and topic in text:
                self._hint_service.mark_used(int(hint.get("id") or 0))
