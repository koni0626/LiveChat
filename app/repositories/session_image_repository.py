from ..utils import json_util
from ..extensions import db
from ..models.chat_session import ChatSession
from ..models.live_chat_room import LiveChatRoom
from ..models.session_image import SessionImage


class SessionImageRepository:
    COSTUME_TYPES = {"costume_initial", "costume_reference"}

    def list_by_session(self, session_id: int):
        return (
            SessionImage.query.filter(SessionImage.session_id == session_id)
            .order_by(SessionImage.id.desc())
            .all()
        )

    def list_costumes_by_session(self, session_id: int):
        return (
            SessionImage.query.filter(
                SessionImage.session_id == session_id,
                SessionImage.image_type.in_(self.COSTUME_TYPES),
            )
            .order_by(SessionImage.id.desc())
            .all()
        )

    def list_costumes_for_session_library(self, session_id: int):
        session = ChatSession.query.get(session_id)
        if not session:
            return []
        room = LiveChatRoom.query.get(session.room_id) if getattr(session, "room_id", None) else None
        character_id = getattr(room, "character_id", None)
        if not character_id:
            return self.list_costumes_by_session(session_id)
        return (
            SessionImage.query.filter(
                SessionImage.image_type.in_(self.COSTUME_TYPES),
                db.or_(
                    SessionImage.session_id == session_id,
                    db.and_(
                        SessionImage.owner_user_id == session.owner_user_id,
                        SessionImage.character_id == character_id,
                        SessionImage.image_type == "costume_reference",
                    ),
                ),
            )
            .order_by((SessionImage.session_id == session_id).desc(), SessionImage.id.desc())
            .all()
        )

    def get(self, session_image_id: int):
        return SessionImage.query.get(session_image_id)

    def create_for_session(self, session_id: int, payload: dict):
        state_json = payload.get("state_json")
        if isinstance(state_json, (dict, list)):
            state_json = json_util.dumps(state_json)
        is_reference = 1 if payload.get("is_reference", 0) else 0
        if is_reference:
            SessionImage.query.filter(SessionImage.session_id == session_id).update({"is_reference": 0})
        row = SessionImage(
            session_id=session_id,
            asset_id=payload["asset_id"],
            owner_user_id=payload.get("owner_user_id"),
            character_id=payload.get("character_id"),
            linked_from_image_id=payload.get("linked_from_image_id"),
            image_type=payload.get("image_type", "live_scene"),
            prompt_text=payload.get("prompt_text"),
            state_json=state_json,
            quality=payload.get("quality"),
            size=payload.get("size"),
            is_selected=payload.get("is_selected", 0),
            is_reference=is_reference,
        )
        db.session.add(row)
        db.session.commit()
        return row

    def create_costume_link_for_session(self, session_id: int, source_image_id: int):
        source = self.get(source_image_id)
        if not source or source.image_type not in self.COSTUME_TYPES:
            return None
        existing = (
            SessionImage.query.filter(
                SessionImage.session_id == session_id,
                SessionImage.linked_from_image_id == source.id,
                SessionImage.image_type.in_(self.COSTUME_TYPES),
            )
            .order_by(SessionImage.id.desc())
            .first()
        )
        if existing:
            return existing
        return self.create_for_session(
            session_id,
            {
                "asset_id": source.asset_id,
                "owner_user_id": source.owner_user_id,
                "character_id": source.character_id,
                "linked_from_image_id": source.id,
                "image_type": "costume_reference",
                "prompt_text": source.prompt_text,
                "state_json": json_util.loads(source.state_json) if source.state_json else None,
                "quality": source.quality,
                "size": source.size,
                "is_selected": 0,
                "is_reference": 0,
            },
        )

    def select(self, session_image_id: int):
        row = self.get(session_image_id)
        if not row:
            return None
        if row.image_type in self.COSTUME_TYPES:
            query = SessionImage.query.filter(
                SessionImage.session_id == row.session_id,
                SessionImage.image_type.in_(self.COSTUME_TYPES),
                SessionImage.id != row.id,
            )
        else:
            query = SessionImage.query.filter(
                SessionImage.session_id == row.session_id,
                ~SessionImage.image_type.in_(self.COSTUME_TYPES),
                SessionImage.id != row.id,
            )
        query.update({"is_selected": 0}, synchronize_session=False)
        row.is_selected = 1
        db.session.commit()
        return row

    def get_selected_costume(self, session_id: int):
        return (
            SessionImage.query.filter(
                SessionImage.session_id == session_id,
                SessionImage.image_type.in_(self.COSTUME_TYPES),
                SessionImage.is_selected == 1,
            )
            .order_by(SessionImage.id.desc())
            .first()
        )

    def delete_costume(self, session_id: int, session_image_id: int):
        row = (
            SessionImage.query.filter(
                SessionImage.id == session_image_id,
                SessionImage.session_id == session_id,
                SessionImage.image_type.in_(self.COSTUME_TYPES),
            ).first()
        )
        if not row:
            return None
        was_selected = bool(row.is_selected)
        db.session.delete(row)
        db.session.flush()
        replacement = None
        if was_selected:
            replacement = (
                SessionImage.query.filter(
                    SessionImage.session_id == session_id,
                    SessionImage.image_type.in_(self.COSTUME_TYPES),
                )
                .order_by(SessionImage.id.desc())
                .first()
            )
            if replacement:
                replacement.is_selected = 1
        db.session.commit()
        return {"deleted_id": session_image_id, "selected_id": replacement.id if replacement else None}

    def set_reference(self, session_id: int, session_image_id: int, is_reference: bool):
        row = (
            SessionImage.query.filter(
                SessionImage.id == session_image_id,
                SessionImage.session_id == session_id,
            ).first()
        )
        if not row:
            return None
        if is_reference:
            SessionImage.query.filter(SessionImage.session_id == session_id).update({"is_reference": 0})
            row.is_reference = 1
        else:
            row.is_reference = 0
        db.session.commit()
        return row
