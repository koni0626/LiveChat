from __future__ import annotations

from ..clients.text_ai_client import TextAIClient
from . import live_chat_text_support as text_support
from .chat_message_service import ChatMessageService
from .chat_session_service import ChatSessionService
from .live_chat_media_service import LiveChatMediaService
from .live_chat_room_service import LiveChatRoomService
from .live_chat_serializer import LiveChatSerializer
from .project_service import ProjectService
from .session_gift_event_service import SessionGiftEventService
from .session_image_service import SessionImageService
from .session_state_service import SessionStateService
from .world_service import WorldService


class LiveChatContextService:
    """Builds live chat context payloads used by UI and AI prompts."""

    def __init__(
        self,
        *,
        chat_session_service: ChatSessionService,
        chat_message_service: ChatMessageService,
        session_state_service: SessionStateService,
        session_image_service: SessionImageService,
        session_gift_event_service: SessionGiftEventService,
        project_service: ProjectService,
        live_chat_room_service: LiveChatRoomService,
        world_service: WorldService,
        serializer: LiveChatSerializer,
        media_service: LiveChatMediaService,
        gift_event_serializer,
        select_characters,
        text_ai_client: TextAIClient,
    ):
        self._chat_session_service = chat_session_service
        self._chat_message_service = chat_message_service
        self._session_state_service = session_state_service
        self._session_image_service = session_image_service
        self._session_gift_event_service = session_gift_event_service
        self._project_service = project_service
        self._live_chat_room_service = live_chat_room_service
        self._world_service = world_service
        self._serializer = serializer
        self._media_service = media_service
        self._gift_event_serializer = gift_event_serializer
        self._select_characters = select_characters
        self._text_ai_client = text_ai_client

    def _create_opening_message(self, session, context: dict):
        opening = text_support.generate_opening_message(self._text_ai_client, context)
        self._chat_message_service.create_message(
            session.id,
            {
                "sender_type": "character",
                "speaker_name": opening["speaker_name"],
                "message_text": opening["message_text"],
                "message_role": "assistant",
            },
        )

    def list_sessions(
        self,
        project_id: int,
        owner_user_id: int | None = None,
        include_private_details: bool = True,
        detail_owner_user_id: int | None = None,
        room_id: int | None = None,
    ):
        items = (
            self._chat_session_service.list_sessions_by_room(room_id, owner_user_id=owner_user_id)
            if room_id
            else self._chat_session_service.list_sessions(project_id, owner_user_id=owner_user_id)
        )
        serialized = []
        for item in items:
            can_include_details = include_private_details or (
                detail_owner_user_id is not None and getattr(item, "owner_user_id", None) == detail_owner_user_id
            )
            messages = self._chat_message_service.list_messages(item.id)
            images = self._session_image_service.list_session_images(item.id)
            scene_images = [
                image
                for image in images
                if image.image_type not in {"costume_initial", "costume_reference"}
            ]
            selected_image_row = next((image for image in scene_images if image.is_selected), None)
            session_characters = self._select_characters(item.id)
            serialized.append(
                {
                    **self._serializer.serialize_session(item),
                    "message_count": len(messages),
                    "last_message_text": messages[-1].message_text if messages and can_include_details else None,
                    "characters": session_characters,
                    "selected_image": (
                        self._media_service.serialize_session_image(selected_image_row)
                        if selected_image_row and can_include_details
                        else None
                    ),
                }
            )
        return serialized

    def get_session_context(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        project = self._project_service.get_project(session.project_id)
        room = self._live_chat_room_service.get_room(session.room_id) if getattr(session, "room_id", None) else None
        state = self._session_state_service.get_state(session_id)
        messages = self._chat_message_service.list_messages(session_id)
        images = self._session_image_service.list_session_images(session_id)
        local_costumes = self._session_image_service.list_costumes(session_id)
        if not local_costumes:
            self._media_service.ensure_initial_costume(session_id)
            images = self._session_image_service.list_session_images(session_id)
        costumes = self._media_service.list_costumes(session_id)
        gift_events = self._session_gift_event_service.list_gift_events(session_id)
        costume_types = {"costume_initial", "costume_reference"}
        scene_images = [item for item in images if item.image_type not in costume_types]
        selected_image = next((item for item in scene_images if item.is_selected), None)
        if not selected_image and scene_images:
            selected_image = scene_images[0]
        characters = self._select_characters(session_id)
        world = self._world_service.get_world(session.project_id)
        if not messages and characters:
            opening_context = {
                "project": {
                    "id": project.id if project else session.project_id,
                    "title": project.title if project else None,
                    "genre": project.genre if project else None,
                },
                "story_outline": {},
                "world": {
                    "name": getattr(world, "name", None) if world else None,
                    "overview": getattr(world, "overview", None) if world else None,
                    "tone": getattr(world, "tone", None) if world else None,
                },
                "session": self._serializer.serialize_session(session),
                "messages": [],
                "state": self._serializer.serialize_state(state),
                "characters": characters,
                "room": self._live_chat_room_service.serialize_room(room) if room else None,
            }
            self._create_opening_message(session, opening_context)
            messages = self._chat_message_service.list_messages(session_id)
        return {
            "project": {
                "id": project.id if project else session.project_id,
                "title": project.title if project else None,
                "genre": project.genre if project else None,
            },
            "story_outline": {},
            "world": {
                "name": getattr(world, "name", None) if world else None,
                "overview": getattr(world, "overview", None) if world else None,
                "tone": getattr(world, "tone", None) if world else None,
            },
            "session": self._serializer.serialize_session(session),
            "room": self._live_chat_room_service.serialize_room(room) if room else None,
            "messages": [self._serializer.serialize_message(item) for item in messages],
            "state": self._serializer.serialize_state(state),
            "characters": characters,
            "images": [self._media_service.serialize_session_image(item) for item in scene_images],
            "costumes": costumes,
            "selected_costume": next((item for item in costumes if item.get("is_selected")), None),
            "gift_events": [self._gift_event_serializer(item) for item in gift_events],
            "selected_image": self._media_service.serialize_session_image(selected_image) if selected_image else None,
        }
