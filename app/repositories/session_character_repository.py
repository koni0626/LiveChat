from ..extensions import db
from ..models.session_character import SessionCharacter


class SessionCharacterRepository:
    def list_by_session(self, session_id: int):
        return (
            SessionCharacter.query.filter(SessionCharacter.session_id == session_id)
            .order_by(SessionCharacter.sort_order.asc(), SessionCharacter.id.asc())
            .all()
        )

    def replace_for_session(self, session_id: int, character_ids: list[int]):
        SessionCharacter.query.filter(SessionCharacter.session_id == session_id).delete()
        rows = [
            SessionCharacter(session_id=session_id, character_id=character_id, sort_order=index)
            for index, character_id in enumerate(character_ids, start=1)
        ]
        if rows:
            db.session.add_all(rows)
        db.session.commit()
        return rows
