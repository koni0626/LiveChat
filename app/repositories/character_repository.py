from datetime import datetime

from ..extensions import db
from ..models.character import Character

class CharacterRepository:
    def list_by_project(self, project_id: int, include_deleted: bool = False):
        query = Character.query.filter(Character.project_id == project_id)
        if not include_deleted:
            query = query.filter(Character.deleted_at.is_(None))
        return query.order_by(Character.id.asc()).all()

    def get(self, character_id: int, include_deleted: bool = False):
        query = Character.query.filter(Character.id == character_id)
        if not include_deleted:
            query = query.filter(Character.deleted_at.is_(None))
        return query.first()

    def create(self, project_id: int, payload: dict):
        character = Character(
            project_id=project_id,
            name=payload["name"],
            role=payload.get("role"),
            age_impression=payload.get("age_impression"),
            first_person=payload.get("first_person"),
            second_person=payload.get("second_person"),
            personality=payload.get("personality"),
            speech_style=payload.get("speech_style"),
            speech_sample=payload.get("speech_sample"),
            ng_rules=payload.get("ng_rules"),
            appearance_summary=payload.get("appearance_summary"),
            base_asset_id=payload.get("base_asset_id"),
            is_guide=payload.get("is_guide", 0),
        )
        db.session.add(character)
        db.session.commit()
        return character

    def update(self, character_id: int, payload: dict):
        character = self.get(character_id, include_deleted=True)
        if not character or character.deleted_at is not None:
            return None
        for field in (
            "name",
            "role",
            "age_impression",
            "first_person",
            "second_person",
            "personality",
            "speech_style",
            "speech_sample",
            "ng_rules",
            "appearance_summary",
            "base_asset_id",
            "is_guide",
        ):
            if field in payload:
                setattr(character, field, payload[field])
        db.session.commit()
        return character

    def delete(self, character_id: int):
        character = self.get(character_id, include_deleted=True)
        if not character:
            return False
        if character.deleted_at is not None:
            return True
        character.deleted_at = datetime.utcnow()
        db.session.commit()
        return True

    def restore(self, character_id: int):
        character = self.get(character_id, include_deleted=True)
        if not character or character.deleted_at is None:
            return None
        character.deleted_at = None
        db.session.commit()
        return character
