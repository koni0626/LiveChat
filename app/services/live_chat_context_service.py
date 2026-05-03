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
from .world_map_service import WorldMapService
from .character_user_memory_service import CharacterUserMemoryService
from .character_memory_note_service import CharacterMemoryNoteService
from .session_objective_note_service import SessionObjectiveNoteService
from .world_news_service import WorldNewsService
from ..repositories.character_repository import CharacterRepository
from ..repositories.feed_repository import FeedRepository
from ..repositories.outing_session_repository import OutingSessionRepository


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
        world_map_service: WorldMapService | None = None,
        serializer: LiveChatSerializer,
        media_service: LiveChatMediaService,
        gift_event_serializer,
        select_characters,
        text_ai_client: TextAIClient,
        character_user_memory_service: CharacterUserMemoryService | None = None,
        character_memory_note_service: CharacterMemoryNoteService | None = None,
        session_objective_note_service: SessionObjectiveNoteService | None = None,
        world_news_service: WorldNewsService | None = None,
        character_repository: CharacterRepository | None = None,
        feed_repository: FeedRepository | None = None,
        outing_repository: OutingSessionRepository | None = None,
    ):
        self._chat_session_service = chat_session_service
        self._chat_message_service = chat_message_service
        self._session_state_service = session_state_service
        self._session_image_service = session_image_service
        self._session_gift_event_service = session_gift_event_service
        self._project_service = project_service
        self._live_chat_room_service = live_chat_room_service
        self._world_service = world_service
        self._world_map_service = world_map_service or WorldMapService()
        self._serializer = serializer
        self._media_service = media_service
        self._gift_event_serializer = gift_event_serializer
        self._select_characters = select_characters
        self._text_ai_client = text_ai_client
        self._character_user_memory_service = character_user_memory_service or CharacterUserMemoryService()
        self._character_memory_note_service = character_memory_note_service or CharacterMemoryNoteService()
        self._session_objective_note_service = session_objective_note_service or SessionObjectiveNoteService()
        self._world_news_service = world_news_service or WorldNewsService()
        self._character_repository = character_repository or CharacterRepository()
        self._feed_repository = feed_repository or FeedRepository()
        self._outing_repository = outing_repository or OutingSessionRepository()

    def _attach_character_growth_notes(self, user_id: int, characters: list[dict]) -> list[dict]:
        enriched = []
        for character in characters or []:
            item = dict(character)
            character_id = int(item.get("id") or 0)
            if character_id:
                item["ai_memory_notes"] = self._character_memory_note_service.list_serialized_notes(
                    user_id,
                    character_id,
                    include_disabled=False,
                    limit=12,
                )
                prompt_block = self._character_memory_note_service.build_prompt_block(
                    user_id,
                    character_id,
                    limit=8,
                )
                cinema_notes = [
                    note
                    for note in item["ai_memory_notes"]
                    if str(note.get("source_type") or "").startswith("cinema_novel")
                ][:4]
                if cinema_notes:
                    cinema_block = "\n".join(
                        [
                            "Recent cinema viewing memories:",
                            *[f"- {note.get('note') or ''}" for note in cinema_notes if note.get("note")],
                            "Use these when the player mentions the reviewed work, its characters, or related topics.",
                        ]
                    )
                    prompt_block = "\n".join(part for part in [prompt_block, cinema_block] if part)
                item["ai_memory_prompt_block"] = prompt_block
            else:
                item["ai_memory_notes"] = []
                item["ai_memory_prompt_block"] = ""
            enriched.append(item)
        return enriched

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
        characters = self._attach_character_growth_notes(session.owner_user_id, self._select_characters(session_id))
        session_objective_notes = self._session_objective_note_service.list_serialized_notes(
            session_id,
            characters=characters,
            include_archived=False,
        )
        session_objective_prompt_block = self._session_objective_note_service.build_prompt_block(
            session_id,
            characters=characters,
        )
        character_user_memories = {}
        for character in characters:
            character_id = int(character.get("id") or 0)
            if not character_id:
                continue
            row = self._character_user_memory_service.get_memory(session.owner_user_id, character_id)
            character_user_memories[str(character_id)] = self._character_user_memory_service.serialize_memory(row)
        world = self._world_service.get_world(session.project_id)
        world_map_context = self._world_map_context(session.project_id)
        world_activity_context = self._world_activity_context(session.project_id, session.owner_user_id, characters)
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
                "world_map": world_map_context,
                "world_activity": world_activity_context,
                "session": self._serializer.serialize_session(session),
                "character_user_memories": character_user_memories,
                "session_objective_notes": session_objective_notes,
                "session_objective_prompt_block": session_objective_prompt_block,
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
            "world_map": world_map_context,
            "world_activity": world_activity_context,
            "session": self._serializer.serialize_session(session),
            "character_user_memories": character_user_memories,
            "session_objective_notes": session_objective_notes,
            "session_objective_prompt_block": session_objective_prompt_block,
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

    def _world_map_context(self, project_id: int):
        try:
            locations = self._world_map_service.list_locations(project_id)
            return {
                "locations": locations[:100],
                "prompt_context": self._world_map_service.location_prompt_context(project_id, limit=20),
            }
        except Exception:
            return {"locations": [], "prompt_context": ""}

    def _world_activity_context(self, project_id: int, user_id: int, characters: list[dict] | None = None):
        character_names = {
            int(character.get("id")): character.get("name")
            for character in characters or []
            if character.get("id")
        }
        try:
            for character in self._character_repository.list_by_project(project_id):
                if getattr(character, "id", None):
                    character_names[int(character.id)] = character.name
        except Exception:
            pass
        location_names = {}
        try:
            location_names = {
                int(location.get("id")): location.get("name")
                for location in self._world_map_service.list_locations(project_id)
                if location.get("id")
            }
        except Exception:
            location_names = {}
        news_items = []
        feed_posts = []
        outings = []
        try:
            for item in self._world_news_service.list_news(project_id, limit=8):
                if not item:
                    continue
                news_items.append(
                    {
                        "title": item.get("title"),
                        "summary": item.get("summary") or item.get("body"),
                        "news_type": item.get("news_type_label") or item.get("news_type"),
                        "character": (item.get("related_character") or {}).get("name"),
                        "location": (item.get("related_location") or {}).get("name"),
                    }
                )
        except Exception:
            news_items = []
        try:
            for post in self._feed_repository.list_posts(
                project_id=project_id,
                statuses=["published"],
                limit=10,
            ):
                feed_posts.append(
                    {
                        "character_id": post.character_id,
                        "character": character_names.get(post.character_id),
                        "body": str(post.body or "")[:220],
                        "like_count": post.like_count or 0,
                    }
                )
        except Exception:
            feed_posts = []
        try:
            for row in self._outing_repository.list_by_project_user(project_id, user_id, limit=8):
                if getattr(row, "status", None) != "completed":
                    continue
                summary = str(getattr(row, "memory_summary", None) or getattr(row, "summary", None) or "").strip()
                if not summary:
                    continue
                outings.append(
                    {
                        "id": row.id,
                        "character_id": row.character_id,
                        "character": character_names.get(row.character_id),
                        "location_id": row.location_id,
                        "location": location_names.get(row.location_id),
                        "title": getattr(row, "memory_title", None) or getattr(row, "title", None),
                        "summary": summary[:260],
                        "mood": getattr(row, "mood", None),
                        "completed_at": row.completed_at.isoformat() if getattr(row, "completed_at", None) else None,
                    }
                )
        except Exception:
            outings = []
        lines = []
        if outings:
            lines.append("Recent completed outings with this player:")
            for item in outings[:8]:
                parts = [f"- {item.get('title') or 'outing memory'}"]
                if item.get("character"):
                    parts.append(f"character: {item['character']}")
                if item.get("location"):
                    parts.append(f"location: {item['location']}")
                if item.get("mood"):
                    parts.append(f"mood: {item['mood']}")
                if item.get("summary"):
                    parts.append(f"summary: {item['summary']}")
                lines.append(" / ".join(parts))
        if news_items:
            lines.append("Recent world news / rumors:")
            for item in news_items[:8]:
                parts = [f"- {item.get('title') or ''}"]
                if item.get("news_type"):
                    parts.append(f"type: {item['news_type']}")
                if item.get("character"):
                    parts.append(f"character: {item['character']}")
                if item.get("location"):
                    parts.append(f"location: {item['location']}")
                if item.get("summary"):
                    parts.append(f"summary: {str(item['summary'])[:220]}")
                lines.append(" / ".join(parts))
        if feed_posts:
            lines.append("Recent Feed posts:")
            for item in feed_posts[:10]:
                parts = [f"- {item.get('character') or 'unknown character'}"]
                if item.get("body"):
                    parts.append(f"post: {item['body']}")
                parts.append(f"likes: {item.get('like_count') or 0}")
                lines.append(" / ".join(parts))
        return {
            "news": news_items,
            "feed_posts": feed_posts,
            "outings": outings,
            "prompt_context": "\n".join(lines),
        }
