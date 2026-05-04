from __future__ import annotations

from datetime import datetime

from ..extensions import db
from ..models.session_character_affinity import SessionCharacterAffinity
from .character_user_memory_service import (
    _clamp_int,
    affinity_label_for_score,
    physical_closeness_label_for_level,
    physical_closeness_level_for_score,
)


class SessionCharacterAffinityService:
    def get_affinity(self, session_id: int, character_id: int):
        if not session_id or not character_id:
            return None
        return SessionCharacterAffinity.query.filter_by(
            session_id=session_id,
            character_id=character_id,
        ).first()

    def get_or_create_affinity(
        self,
        *,
        session_id: int,
        user_id: int,
        project_id: int,
        character_id: int,
    ):
        row = self.get_affinity(session_id, character_id)
        if row:
            return row
        row = SessionCharacterAffinity(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            character_id=character_id,
            affinity_score=0,
            affinity_label=affinity_label_for_score(0),
            physical_closeness_level=0,
            locked_at_100=False,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def serialize_affinity(self, row) -> dict:
        if not row:
            return {
                "affinity_score": 0,
                "affinity_label": affinity_label_for_score(0),
                "affinity_notes": "",
                "physical_closeness_level": 0,
                "physical_closeness_label": physical_closeness_label_for_level(0),
                "locked_at_100": False,
                "reached_100_at": None,
                "last_interaction_at": None,
                "scope": "session",
            }
        level = _clamp_int(row.physical_closeness_level or 0, 0, 5)
        return {
            "id": row.id,
            "session_id": row.session_id,
            "user_id": row.user_id,
            "project_id": row.project_id,
            "character_id": row.character_id,
            "affinity_score": _clamp_int(row.affinity_score or 0, 0, 100),
            "affinity_label": row.affinity_label or affinity_label_for_score(row.affinity_score or 0),
            "affinity_notes": row.affinity_notes or "",
            "physical_closeness_level": level,
            "physical_closeness_label": physical_closeness_label_for_level(level),
            "locked_at_100": bool(row.locked_at_100),
            "reached_100_at": row.reached_100_at.isoformat() if row.reached_100_at else None,
            "last_interaction_at": row.last_interaction_at.isoformat() if row.last_interaction_at else None,
            "scope": "session",
        }

    def list_serialized_affinities(
        self,
        *,
        session_id: int,
        user_id: int,
        project_id: int,
        character_ids: list[int],
    ) -> dict:
        result = {}
        for character_id in character_ids or []:
            row = self.get_or_create_affinity(
                session_id=session_id,
                user_id=user_id,
                project_id=project_id,
                character_id=int(character_id),
            )
            result[str(character_id)] = self.serialize_affinity(row)
        return result

    def update_affinity_from_ai_evaluation(
        self,
        *,
        session_id: int,
        user_id: int,
        project_id: int,
        character_id: int,
        affinity_delta: int = 0,
        reason: str | None = None,
        physical_closeness_delta: int = 0,
    ):
        row = self.get_or_create_affinity(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            character_id=character_id,
        )
        current_score = _clamp_int(row.affinity_score or 0, 0, 100)
        delta = _clamp_int(affinity_delta or 0, -12, 12)
        if row.locked_at_100 or current_score >= 100:
            next_score = 100
            row.locked_at_100 = True
            row.reached_100_at = row.reached_100_at or datetime.utcnow()
            delta = max(0, delta)
        else:
            next_score = _clamp_int(current_score + delta, 0, 100)
            if next_score >= 100:
                next_score = 100
                row.locked_at_100 = True
                row.reached_100_at = datetime.utcnow()
        row.affinity_score = next_score
        row.affinity_label = affinity_label_for_score(next_score)
        base_level = physical_closeness_level_for_score(next_score)
        if physical_closeness_delta:
            base_level = _clamp_int(base_level + int(physical_closeness_delta), 0, 5)
        row.physical_closeness_level = base_level
        sign = "+" if delta >= 0 else ""
        note = str(reason or "AI affinity evaluation").strip()
        row.affinity_notes = f"{datetime.utcnow().isoformat(timespec='seconds')}Z {sign}{delta}: {note}"[:1000]
        row.last_interaction_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row

    def force_affinity_100(
        self,
        *,
        session_id: int,
        user_id: int,
        project_id: int,
        character_id: int,
        reason: str | None = None,
    ):
        row = self.get_or_create_affinity(
            session_id=session_id,
            user_id=user_id,
            project_id=project_id,
            character_id=character_id,
        )
        row.affinity_score = 100
        row.affinity_label = affinity_label_for_score(100)
        row.physical_closeness_level = physical_closeness_level_for_score(100)
        row.locked_at_100 = True
        row.reached_100_at = row.reached_100_at or datetime.utcnow()
        row.affinity_notes = (
            f"{datetime.utcnow().isoformat(timespec='seconds')}Z +debug: "
            f"{str(reason or 'debug shortcut clear').strip()}"
        )[:1000]
        row.last_interaction_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row
