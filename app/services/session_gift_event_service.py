from ..utils import json_util
from ..repositories.session_gift_event_repository import SessionGiftEventRepository


class SessionGiftEventService:
    def __init__(self, repository: SessionGiftEventRepository | None = None):
        self._repo = repository or SessionGiftEventRepository()

    def list_gift_events(self, session_id: int):
        return self._repo.list_by_session(session_id)

    def create_gift_event(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        tags = payload.get("recognized_tags_json")
        if isinstance(tags, (dict, list)):
            payload["recognized_tags_json"] = json_util.dumps(tags)
        payload["session_id"] = session_id
        return self._repo.create(payload)
