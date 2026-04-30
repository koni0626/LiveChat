from __future__ import annotations

from .character_service import CharacterService
from .chat_message_service import ChatMessageService
from .chat_session_service import ChatSessionService
from .live_chat_conversation_service import LiveChatConversationService
from .live_chat_media_service import LiveChatMediaService
from .live_chat_room_service import LiveChatRoomService
from .live_chat_serializer import LiveChatSerializer
from .session_state_service import SessionStateService


class LiveChatSessionWorkflowService:
    """Session creation/update workflows that sit above low-level repositories."""

    def __init__(
        self,
        *,
        chat_session_service: ChatSessionService,
        chat_message_service: ChatMessageService,
        session_state_service: SessionStateService,
        character_service: CharacterService,
        live_chat_room_service: LiveChatRoomService,
        media_service: LiveChatMediaService,
        conversation_service: LiveChatConversationService,
        serializer: LiveChatSerializer,
        context_provider,
    ):
        self._chat_session_service = chat_session_service
        self._chat_message_service = chat_message_service
        self._session_state_service = session_state_service
        self._character_service = character_service
        self._live_chat_room_service = live_chat_room_service
        self._media_service = media_service
        self._conversation_service = conversation_service
        self._serializer = serializer
        self._context_provider = context_provider

    def selected_character_ids_from_session(self, session) -> list[int]:
        room_snapshot = self._serializer.load_json(getattr(session, "room_snapshot_json", None)) or {}
        if isinstance(room_snapshot, dict):
            try:
                room_character_id = int(room_snapshot.get("character_id") or 0)
            except (TypeError, ValueError):
                room_character_id = 0
            if room_character_id > 0:
                return [room_character_id]

        settings_json = self._serializer.load_json(getattr(session, "settings_json", None)) or {}
        if not isinstance(settings_json, dict):
            return []
        raw_value = settings_json.get("selected_character_ids")
        if raw_value is None and settings_json.get("selected_character_id") is not None:
            raw_value = [settings_json.get("selected_character_id")]
        if not isinstance(raw_value, list):
            return []
        normalized = []
        seen = set()
        for item in raw_value:
            try:
                character_id = int(item)
            except (TypeError, ValueError):
                continue
            if character_id <= 0 or character_id in seen:
                continue
            seen.add(character_id)
            normalized.append(character_id)
        return normalized

    def select_characters(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return []
        all_characters = self._character_service.list_characters(session.project_id)
        selected_ids = set(self.selected_character_ids_from_session(session))
        scoped_characters = [
            character for character in all_characters
            if not selected_ids or character.id in selected_ids
        ]
        target_characters = scoped_characters or all_characters
        return [self._serializer.serialize_character(character) for character in target_characters]

    def create_session(self, project_id: int, payload: dict | None = None, owner_user_id: int | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.create_session(project_id, payload, owner_user_id=owner_user_id)
        if not session:
            return None
        initial_state = {}
        selected_character_ids = self.selected_character_ids_from_session(session)
        if selected_character_ids:
            initial_state["active_character_ids"] = selected_character_ids
        self._session_state_service.upsert_state(session.id, {"state_json": initial_state})
        return self._context_provider(session.id)

    def create_session_from_room(self, room_id: int, payload: dict | None = None, owner_user_id: int | None = None):
        payload = dict(payload or {})
        if not owner_user_id:
            raise ValueError("owner_user_id is required")
        room = self._live_chat_room_service.get_room(room_id)
        if not room:
            return None
        player_name = str(payload.get("player_name") or "").strip()
        if not player_name:
            raise ValueError("player_name is required")
        snapshot = self._live_chat_room_service.build_room_snapshot(room)
        title = str(payload.get("title") or "").strip()
        if not title:
            title = f"{snapshot.get('character_name') or room.title}との会話"
        session_payload = {
            "room_id": room.id,
            "title": title,
            "player_name": player_name,
            "settings_json": {
                "selected_character_ids": [room.character_id],
                "conversation_objective": room.conversation_objective,
                "proxy_player_objective": getattr(room, "proxy_player_objective", None),
                "proxy_player_gender": getattr(room, "proxy_player_gender", None),
                "proxy_player_speech_style": getattr(room, "proxy_player_speech_style", None),
            },
            "room_snapshot_json": snapshot,
        }
        session = self._chat_session_service.create_session(room.project_id, session_payload, owner_user_id=owner_user_id)
        if not session:
            return None
        self._session_state_service.upsert_state(
            session.id,
            {
                "state_json": {
                    "active_character_ids": [room.character_id],
                    "room_id": room.id,
                }
            },
        )
        if getattr(room, "default_outfit_id", None):
            self._media_service.select_closet_outfit(session.id, int(room.default_outfit_id))
        else:
            self._media_service.ensure_initial_costume(session.id)
        return self._context_provider(session.id)

    def _preserve_locked_session_characters(self, session_id: int, payload: dict) -> dict:
        if "settings_json" not in payload:
            return payload
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return payload
        locked_character_ids = self.selected_character_ids_from_session(session)
        settings_json = self._serializer.load_json(payload.get("settings_json")) or {}
        if not isinstance(settings_json, dict):
            settings_json = {}
        settings_json.pop("selected_character_id", None)
        if locked_character_ids:
            settings_json["selected_character_ids"] = locked_character_ids
        else:
            settings_json.pop("selected_character_ids", None)
        payload["settings_json"] = settings_json
        return payload

    def update_session(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        payload = self._preserve_locked_session_characters(session_id, payload)
        session = self._chat_session_service.update_session(session_id, payload)
        if not session:
            return None
        selected_character_ids = self.selected_character_ids_from_session(session)
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._serializer.load_json(getattr(state_row, "state_json", None)) or {}
        if selected_character_ids:
            state_json["active_character_ids"] = selected_character_ids
        else:
            state_json.pop("active_character_ids", None)
        self._session_state_service.upsert_state(session_id, {"state_json": state_json})
        return self._context_provider(session_id)

    def delete_message(self, session_id: int, message_id: int):
        row = self._chat_message_service.delete_message(message_id)
        if not row or row.session_id != session_id:
            return None
        context = self._context_provider(session_id)
        self._conversation_service.update_conversation_evaluation(session_id, context)
        return self._context_provider(session_id)

    def extract_state(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        context = self._context_provider(session_id)
        state = self._session_state_service.extract_state(
            session=session,
            messages=context["messages"],
            characters=context["characters"],
        )
        return self._serializer.serialize_state(state)
