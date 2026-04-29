from ..extensions import db
from ..models.story_session_state import StorySessionState


class StorySessionStateRepository:
    def get_by_session(self, session_id: int):
        return StorySessionState.query.filter(StorySessionState.session_id == session_id).first()

    def upsert(self, session_id: int, payload: dict):
        row = self.get_by_session(session_id)
        if row is None:
            row = StorySessionState(
                session_id=session_id,
                state_json=payload.get("state_json") or "{}",
                version=payload.get("version") or 1,
            )
            db.session.add(row)
        else:
            if "state_json" in payload:
                row.state_json = payload["state_json"]
            if "version" in payload:
                row.version = payload["version"]
            else:
                row.version = int(row.version or 0) + 1
        db.session.commit()
        return row
