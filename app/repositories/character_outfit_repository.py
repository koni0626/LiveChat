from datetime import datetime

from ..extensions import db
from ..models.character_outfit import CharacterOutfit


class CharacterOutfitRepository:
    def _order_by_display_priority(self, query, *, include_character: bool = False):
        del include_character
        return query.order_by(CharacterOutfit.id.desc())

    def list_by_project(self, project_id: int, include_deleted: bool = False):
        query = CharacterOutfit.query.filter(CharacterOutfit.project_id == project_id)
        if not include_deleted:
            query = query.filter(CharacterOutfit.deleted_at.is_(None))
        return self._order_by_display_priority(query, include_character=True).all()

    def list_by_character(self, character_id: int, include_deleted: bool = False):
        query = CharacterOutfit.query.filter(CharacterOutfit.character_id == character_id)
        if not include_deleted:
            query = query.filter(CharacterOutfit.deleted_at.is_(None))
        return self._order_by_display_priority(query).all()

    def get(self, outfit_id: int, include_deleted: bool = False):
        query = CharacterOutfit.query.filter(CharacterOutfit.id == outfit_id)
        if not include_deleted:
            query = query.filter(CharacterOutfit.deleted_at.is_(None))
        return query.first()

    def get_default(self, character_id: int):
        return CharacterOutfit.query.filter(
            CharacterOutfit.character_id == character_id,
            CharacterOutfit.is_default.is_(True),
            CharacterOutfit.deleted_at.is_(None),
        ).order_by(CharacterOutfit.id.desc()).first()

    def create(self, payload: dict):
        if payload.get("is_default"):
            self.clear_default(payload["character_id"])
        row = CharacterOutfit(
            project_id=payload["project_id"],
            character_id=payload["character_id"],
            name=payload["name"],
            description=payload.get("description"),
            asset_id=payload["asset_id"],
            thumbnail_asset_id=payload.get("thumbnail_asset_id"),
            source_type=payload.get("source_type") or "outfit",
            tags_json=payload.get("tags_json"),
            usage_scene=payload.get("usage_scene"),
            season=payload.get("season"),
            mood=payload.get("mood"),
            color_notes=payload.get("color_notes"),
            fixed_parts=payload.get("fixed_parts"),
            allowed_changes=payload.get("allowed_changes"),
            ng_rules=payload.get("ng_rules"),
            prompt_notes=payload.get("prompt_notes"),
            is_default=bool(payload.get("is_default")),
            status=payload.get("status") or "active",
        )
        db.session.add(row)
        db.session.commit()
        return row

    def update(self, outfit_id: int, payload: dict):
        row = self.get(outfit_id, include_deleted=True)
        if not row or row.deleted_at is not None:
            return None
        if payload.get("is_default") is True:
            self.clear_default(row.character_id, commit=False)
        for field in (
            "name",
            "description",
            "asset_id",
            "thumbnail_asset_id",
            "source_type",
            "tags_json",
            "usage_scene",
            "season",
            "mood",
            "color_notes",
            "fixed_parts",
            "allowed_changes",
            "ng_rules",
            "prompt_notes",
            "is_default",
            "status",
        ):
            if field in payload:
                setattr(row, field, payload[field])
        db.session.commit()
        return row

    def set_default(self, outfit_id: int):
        row = self.get(outfit_id)
        if not row:
            return None
        self.clear_default(row.character_id, commit=False)
        row.is_default = True
        db.session.commit()
        return row

    def clear_default(self, character_id: int, *, commit: bool = True):
        CharacterOutfit.query.filter(
            CharacterOutfit.character_id == character_id,
            CharacterOutfit.is_default.is_(True),
            CharacterOutfit.deleted_at.is_(None),
        ).update({"is_default": False})
        if commit:
            db.session.commit()

    def delete(self, outfit_id: int):
        row = self.get(outfit_id, include_deleted=True)
        if not row:
            return False
        if row.deleted_at is not None:
            return True
        row.deleted_at = datetime.utcnow()
        db.session.commit()
        return True
