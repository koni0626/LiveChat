from ..utils import json_util
from ..repositories.chat_message_repository import ChatMessageRepository


class ChatMessageService:
    def __init__(self, repository: ChatMessageRepository | None = None):
        self._repo = repository or ChatMessageRepository()

    def list_messages(self, session_id: int):
        return self._repo.list_by_session(session_id)

    def create_message(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        message_text = str(payload.get("message_text") or "").strip()
        if not message_text:
            raise ValueError("message_text is required")
        sender_type = str(payload.get("sender_type") or "user").strip() or "user"
        order_no = self._repo.get_max_order_no(session_id) + 1
        state_snapshot = payload.get("state_snapshot_json")
        if isinstance(state_snapshot, (dict, list)):
            state_snapshot = json_util.dumps(state_snapshot)
        return self._repo.create(
            {
                "session_id": session_id,
                "sender_type": sender_type,
                "speaker_name": (str(payload.get("speaker_name") or "").strip() or None),
                "message_text": message_text,
                "order_no": order_no,
                "message_role": (str(payload.get("message_role") or "").strip() or None),
                "state_snapshot_json": state_snapshot,
            }
        )

    def delete_message(self, message_id: int):
        return self._repo.delete(message_id)
