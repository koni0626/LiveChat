from __future__ import annotations

from .live_chat_genre_support import LEARNING_GENRE, genre_from_session, normalize_live_chat_genre


class LiveChatGenreRouter:
    def __init__(
        self,
        *,
        chat_session_service,
        live_chat_room_service,
        serializer,
        romance_context_service,
        romance_conversation_service,
        learning_context_service,
        learning_conversation_service,
    ):
        self._chat_session_service = chat_session_service
        self._live_chat_room_service = live_chat_room_service
        self._serializer = serializer
        self._romance_context_service = romance_context_service
        self._romance_conversation_service = romance_conversation_service
        self._learning_context_service = learning_context_service
        self._learning_conversation_service = learning_conversation_service

    def genre_for_session(self, session_id: int) -> str:
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return "romance"
        room = self._live_chat_room_service.get_room(session.room_id) if getattr(session, "room_id", None) else None
        return normalize_live_chat_genre(genre_from_session(session, room=room, serializer=self._serializer))

    def is_learning(self, session_id: int) -> bool:
        return self.genre_for_session(session_id) == LEARNING_GENRE

    def get_session_context(self, session_id: int):
        if self.is_learning(session_id):
            return self._learning_context_service.get_session_context(session_id)
        return self._romance_context_service.get_session_context(session_id)

    def post_message(self, session_id: int, payload: dict | None = None):
        if self.is_learning(session_id):
            return self._learning_conversation_service.post_message(session_id, payload)
        return self._romance_conversation_service.post_message(session_id, payload)

    def generate_player_proxy_message(self, session_id: int, payload: dict | None = None):
        if self.is_learning(session_id):
            return self._learning_conversation_service.generate_player_proxy_message(session_id, payload)
        return self._romance_conversation_service.generate_player_proxy_message(session_id, payload)

    def post_idle_character_message(self, session_id: int):
        if self.is_learning(session_id):
            return self._learning_conversation_service.post_idle_character_message(session_id)
        return self._romance_conversation_service.post_idle_character_message(session_id)

    def execute_scene_choice(self, session_id: int, choice_id: str, payload: dict | None = None):
        if self.is_learning(session_id):
            return self._learning_conversation_service.execute_scene_choice(session_id, choice_id, payload)
        return self._romance_conversation_service.execute_scene_choice(session_id, choice_id, payload)
