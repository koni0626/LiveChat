from __future__ import annotations

from datetime import datetime

from ..extensions import db
from ..models import CharacterIntelHint


class CharacterIntelHintService:
    def serialize_hint(self, row, *, target_name: str | None = None, source_name: str | None = None) -> dict:
        return {
            "id": row.id,
            "target_character_id": row.target_character_id,
            "target_character_name": target_name,
            "source_character_id": row.source_character_id,
            "source_character_name": source_name,
            "topic": row.topic,
            "hint_text": row.hint_text,
            "reveal_threshold": row.reveal_threshold,
            "status": row.status,
            "revealed_at": row.revealed_at.isoformat() if row.revealed_at else None,
            "used_at": row.used_at.isoformat() if row.used_at else None,
        }

    def list_revealed_for_targets(self, user_id: int, target_character_ids: list[int]) -> list[CharacterIntelHint]:
        ids = [int(value) for value in target_character_ids or [] if int(value or 0)]
        if not user_id or not ids:
            return []
        return (
            CharacterIntelHint.query.filter(
                CharacterIntelHint.user_id == user_id,
                CharacterIntelHint.target_character_id.in_(ids),
                CharacterIntelHint.status.in_(("revealed", "used")),
            )
            .order_by(CharacterIntelHint.revealed_at.desc(), CharacterIntelHint.id.desc())
            .limit(40)
            .all()
        )

    def existing_topics_for_source(self, user_id: int, source_character_id: int) -> set[tuple[int, str]]:
        rows = CharacterIntelHint.query.filter_by(
            user_id=user_id,
            source_character_id=source_character_id,
        ).all()
        return {(int(row.target_character_id), str(row.topic or "").strip().lower()) for row in rows}

    def upsert_revealed_hint(
        self,
        *,
        user_id: int,
        project_id: int,
        target_character_id: int,
        source_character_id: int,
        topic: str,
        hint_text: str,
        reveal_threshold: int = 40,
    ):
        topic = str(topic or "").strip()[:255]
        hint_text = str(hint_text or "").strip()[:1000]
        if not user_id or not project_id or not target_character_id or not source_character_id or not topic or not hint_text:
            return None
        row = CharacterIntelHint.query.filter_by(
            user_id=user_id,
            target_character_id=target_character_id,
            source_character_id=source_character_id,
            topic=topic,
        ).first()
        if row:
            if row.status == "candidate":
                row.status = "revealed"
            row.hint_text = hint_text
            row.revealed_at = row.revealed_at or datetime.utcnow()
        else:
            row = CharacterIntelHint(
                user_id=user_id,
                project_id=project_id,
                target_character_id=target_character_id,
                source_character_id=source_character_id,
                topic=topic,
                hint_text=hint_text,
                reveal_threshold=int(reveal_threshold or 40),
                status="revealed",
                revealed_at=datetime.utcnow(),
            )
            db.session.add(row)
        db.session.commit()
        return row

    def mark_used(self, hint_id: int):
        row = CharacterIntelHint.query.get(hint_id)
        if not row:
            return None
        row.status = "used"
        row.used_at = row.used_at or datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row
