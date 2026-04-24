from ..extensions import db
from ..models.session_state import SessionState


class SessionStateRepository:
    def get_by_session(self, session_id: int):
        return SessionState.query.filter(SessionState.session_id == session_id).first()

    def upsert(self, session_id: int, payload: dict):
        row = self.get_by_session(session_id)
        if row is None:
            row = SessionState(
                session_id=session_id,
                state_json=payload.get("state_json") or "{}",
                narration_note=payload.get("narration_note"),
                visual_prompt_text=payload.get("visual_prompt_text"),
            )
            db.session.add(row)
        else:
            if "state_json" in payload:
                row.state_json = payload["state_json"]
            if "narration_note" in payload:
                row.narration_note = payload["narration_note"]
            if "visual_prompt_text" in payload:
                row.visual_prompt_text = payload["visual_prompt_text"]
        db.session.commit()
        return row
