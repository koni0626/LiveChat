from __future__ import annotations

from datetime import datetime

from ..extensions import db
from ..models.character_affinity_reward import CharacterAffinityReward
from ..repositories.character_outfit_repository import CharacterOutfitRepository


class CharacterAffinityRewardService:
    def __init__(self, outfit_repository: CharacterOutfitRepository | None = None):
        self._outfit_repository = outfit_repository or CharacterOutfitRepository()

    def get_reward(self, user_id: int, character_id: int):
        return CharacterAffinityReward.query.filter(
            CharacterAffinityReward.user_id == user_id,
            CharacterAffinityReward.character_id == character_id,
        ).first()

    def get_or_create_reward(self, user_id: int, project_id: int, character_id: int):
        row = self.get_reward(user_id, character_id)
        if row:
            if int(row.project_id or 0) != int(project_id or 0):
                row.project_id = project_id
                db.session.commit()
            return row
        row = CharacterAffinityReward(
            user_id=user_id,
            project_id=project_id,
            character_id=character_id,
            costume_ticket_balance=0,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def serialize_reward(self, row, *, session_id: int | None = None) -> dict:
        if not row:
            return {
                "event_claimed": False,
                "clear_unlocked": False,
                "closet_unlocked": False,
                "event_image_id": None,
                "costume_ticket_balance": 0,
                "costume_ticket_earned_at": None,
                "costume_ticket_used_at": None,
                "lccd_unlocked_for_session": False,
                "saved_outfit_id": None,
            }
        return {
            "id": row.id,
            "user_id": row.user_id,
            "project_id": row.project_id,
            "character_id": row.character_id,
            "event_claimed": bool(row.event_claimed_at),
            "clear_unlocked": bool(row.event_claimed_at),
            "closet_unlocked": bool(row.event_claimed_at),
            "event_image_id": row.event_image_id,
            "event_claimed_at": row.event_claimed_at.isoformat() if row.event_claimed_at else None,
            "costume_ticket_balance": int(row.costume_ticket_balance or 0),
            "costume_ticket_earned_at": (
                row.costume_ticket_earned_at.isoformat() if row.costume_ticket_earned_at else None
            ),
            "costume_ticket_used_at": row.costume_ticket_used_at.isoformat() if row.costume_ticket_used_at else None,
            "lccd_unlocked_session_id": row.lccd_unlocked_session_id,
            "lccd_unlocked_for_session": (
                bool(session_id)
                and bool(row.lccd_unlocked_session_id)
                and int(row.lccd_unlocked_session_id) == int(session_id)
            ),
            "saved_outfit_id": row.saved_outfit_id,
        }

    def list_serialized_rewards(
        self,
        *,
        user_id: int,
        project_id: int,
        character_ids: list[int],
        session_id: int | None = None,
    ) -> dict:
        ids = [int(character_id) for character_id in character_ids or [] if int(character_id or 0)]
        if not ids:
            return {}
        rows = CharacterAffinityReward.query.filter(
            CharacterAffinityReward.user_id == user_id,
            CharacterAffinityReward.character_id.in_(ids),
        ).all()
        by_id = {int(row.character_id): row for row in rows}
        result = {}
        for character_id in ids:
            row = by_id.get(character_id)
            if row and int(row.project_id or 0) != int(project_id or 0):
                row.project_id = project_id
                db.session.commit()
            result[str(character_id)] = self.serialize_reward(row, session_id=session_id)
        return result

    def claim_affinity_100_reward(self, *, user_id: int, project_id: int, character_id: int, event_image_id: int | None):
        row = self.get_or_create_reward(user_id, project_id, character_id)
        if row.event_claimed_at:
            return row, False
        now = datetime.utcnow()
        row.event_image_id = event_image_id
        row.event_claimed_at = now
        row.costume_ticket_balance = int(row.costume_ticket_balance or 0) + 1
        row.costume_ticket_earned_at = now
        db.session.commit()
        return row, True

    def can_enter_lccd(self, *, user_id: int, character_id: int, session_id: int) -> bool:
        row = self.get_reward(user_id, character_id)
        if not row:
            return False
        if row.lccd_unlocked_session_id and int(row.lccd_unlocked_session_id) == int(session_id):
            return True
        return int(row.costume_ticket_balance or 0) > 0

    def unlock_lccd_with_ticket(self, *, user_id: int, character_id: int, session_id: int):
        row = self.get_reward(user_id, character_id)
        if not row:
            return None
        if row.lccd_unlocked_session_id and int(row.lccd_unlocked_session_id) == int(session_id):
            return row
        balance = int(row.costume_ticket_balance or 0)
        if balance <= 0:
            return None
        row.costume_ticket_balance = balance - 1
        row.costume_ticket_used_at = datetime.utcnow()
        row.lccd_unlocked_session_id = session_id
        db.session.commit()
        return row

    def is_lccd_unlocked(self, *, user_id: int, character_id: int, session_id: int) -> bool:
        row = self.get_reward(user_id, character_id)
        return bool(row and row.lccd_unlocked_session_id and int(row.lccd_unlocked_session_id) == int(session_id))

    def register_saved_outfit(self, *, user_id: int, character_id: int, outfit_id: int | None):
        if not outfit_id:
            return None
        row = self.get_reward(user_id, character_id)
        if not row:
            return None
        previous_id = int(row.saved_outfit_id or 0)
        next_id = int(outfit_id)
        if previous_id and previous_id != next_id:
            self._outfit_repository.delete(previous_id)
        row.saved_outfit_id = next_id
        db.session.commit()
        return row
