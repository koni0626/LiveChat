from __future__ import annotations

from datetime import datetime

from ..extensions import db
from ..models import CharacterUserMemory


class CharacterUserMemoryService:
    def get_memory(self, user_id: int, character_id: int):
        if not user_id or not character_id:
            return None
        return CharacterUserMemory.query.filter_by(user_id=user_id, character_id=character_id).first()

    def get_or_create_memory(self, user_id: int, character_id: int):
        row = self.get_memory(user_id, character_id)
        if row:
            return row
        row = CharacterUserMemory(user_id=user_id, character_id=character_id, memory_enabled=True)
        db.session.add(row)
        db.session.commit()
        return row

    def serialize_memory(self, row) -> dict:
        if not row:
            return {}
        return {
            "relationship_summary": row.relationship_summary or "",
            "memory_notes": row.memory_notes or "",
            "preference_notes": row.preference_notes or "",
            "unresolved_threads": row.unresolved_threads or "",
            "important_events": row.important_events or "",
            "last_interaction_at": row.last_interaction_at.isoformat() if row.last_interaction_at else None,
            "memory_enabled": bool(row.memory_enabled),
        }

    def build_prompt_block(self, user_id: int, character_id: int) -> str:
        row = self.get_memory(user_id, character_id)
        if not row or row.memory_enabled is False:
            return ""
        data = self.serialize_memory(row)
        lines = [
            "Character memory about this player:",
            f"relationship_summary: {data['relationship_summary'] or '(none)'}",
            f"shared_memories: {data['memory_notes'] or '(none)'}",
            f"player_preferences: {data['preference_notes'] or '(none)'}",
            f"open_threads: {data['unresolved_threads'] or '(none)'}",
            f"important_events: {data['important_events'] or '(none)'}",
            "Use this memory subtly. Do not mention it unnaturally.",
        ]
        return "\n".join(lines)

    def update_from_event(
        self,
        *,
        user_id: int,
        character_id: int,
        relationship_summary: str | None = None,
        memory_notes: str | None = None,
        preference_notes: str | None = None,
        unresolved_threads: str | None = None,
        important_events: str | None = None,
    ):
        row = self.get_or_create_memory(user_id, character_id)
        if row.memory_enabled is False:
            return row
        if relationship_summary:
            row.relationship_summary = str(relationship_summary).strip()[:1000]
        if memory_notes:
            row.memory_notes = str(memory_notes).strip()[:3000]
        if preference_notes:
            row.preference_notes = str(preference_notes).strip()[:2000]
        if unresolved_threads:
            row.unresolved_threads = str(unresolved_threads).strip()[:2000]
        if important_events:
            merged = "\n".join([item for item in [row.important_events, str(important_events).strip()] if item])
            row.important_events = merged[-4000:]
        row.last_interaction_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row
