from ..utils import json_util
from ..extensions import db
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

    def select(self, session_image_id: int):
        row = self.get(session_image_id)
        if not row:
            return None
        if row.image_type in self.COSTUME_TYPES:
            query = SessionImage.query.filter(
                SessionImage.session_id == row.session_id,
                SessionImage.image_type.in_(self.COSTUME_TYPES),
            )
        else:
            query = SessionImage.query.filter(
                SessionImage.session_id == row.session_id,
                ~SessionImage.image_type.in_(self.COSTUME_TYPES),
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
