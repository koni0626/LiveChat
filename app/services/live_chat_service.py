from __future__ import annotations

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from .asset_service import AssetService
from .character_service import CharacterService
from .chat_message_service import ChatMessageService
from .chat_session_service import ChatSessionService
from .live_chat_room_service import LiveChatRoomService
from .letter_service import LetterService
from .live_chat_conversation_service import LiveChatConversationService
from .live_chat_context_service import LiveChatContextService
from .live_chat_gift_service import LiveChatGiftService
from .live_chat_media_service import LiveChatMediaService
from .live_chat_serializer import LiveChatSerializer
from .live_chat_short_story_service import LiveChatShortStoryService
from .live_chat_session_workflow_service import LiveChatSessionWorkflowService
from .project_service import ProjectService
from .session_gift_event_service import SessionGiftEventService
from .session_image_service import SessionImageService
from .session_state_service import SessionStateService
from .player_reaction_service import PlayerReactionService
from .world_service import WorldService
from .world_map_service import WorldMapService
from .character_user_memory_service import CharacterUserMemoryService
from .character_memory_note_service import CharacterMemoryNoteService
from .session_objective_note_service import SessionObjectiveNoteService


class LiveChatService:
    def __init__(
        self,
        chat_session_service: ChatSessionService | None = None,
        chat_message_service: ChatMessageService | None = None,
        session_state_service: SessionStateService | None = None,
        session_image_service: SessionImageService | None = None,
        project_service: ProjectService | None = None,
        character_service: CharacterService | None = None,
        asset_service: AssetService | None = None,
        session_gift_event_service: SessionGiftEventService | None = None,
        live_chat_room_service: LiveChatRoomService | None = None,
        letter_service: LetterService | None = None,
        world_service: WorldService | None = None,
        world_map_service: WorldMapService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
        character_user_memory_service: CharacterUserMemoryService | None = None,
        character_memory_note_service: CharacterMemoryNoteService | None = None,
        session_objective_note_service: SessionObjectiveNoteService | None = None,
        player_reaction_service: PlayerReactionService | None = None,
    ):
        self._chat_session_service = chat_session_service or ChatSessionService()
        self._chat_message_service = chat_message_service or ChatMessageService()
        self._session_state_service = session_state_service or SessionStateService()
        self._session_image_service = session_image_service or SessionImageService()
        self._project_service = project_service or ProjectService()
        self._character_service = character_service or CharacterService()
        self._asset_service = asset_service or AssetService()
        self._session_gift_event_service = session_gift_event_service or SessionGiftEventService()
        self._live_chat_room_service = live_chat_room_service or LiveChatRoomService()
        self._letter_service = letter_service or LetterService()
        self._world_service = world_service or WorldService()
        self._world_map_service = world_map_service or WorldMapService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._character_user_memory_service = character_user_memory_service or CharacterUserMemoryService()
        self._character_memory_note_service = character_memory_note_service or CharacterMemoryNoteService()
        self._session_objective_note_service = session_objective_note_service or SessionObjectiveNoteService()
        self._player_reaction_service = player_reaction_service or PlayerReactionService(
            text_ai_client=self._text_ai_client,
            session_state_service=self._session_state_service,
        )
        self._serializer = LiveChatSerializer(asset_service=self._asset_service)
        self._media_service = LiveChatMediaService(
            chat_session_service=self._chat_session_service,
            session_state_service=self._session_state_service,
            session_image_service=self._session_image_service,
            asset_service=self._asset_service,
            text_ai_client=self._text_ai_client,
            image_ai_client=self._image_ai_client,
            context_provider=self.get_session_context,
            select_characters=self._select_characters,
        )
        self._context_service = LiveChatContextService(
            chat_session_service=self._chat_session_service,
            chat_message_service=self._chat_message_service,
            session_state_service=self._session_state_service,
            session_image_service=self._session_image_service,
            session_gift_event_service=self._session_gift_event_service,
            project_service=self._project_service,
            live_chat_room_service=self._live_chat_room_service,
            world_service=self._world_service,
            world_map_service=self._world_map_service,
            serializer=self._serializer,
            media_service=self._media_service,
            gift_event_serializer=self._serialize_gift_event,
            select_characters=self._select_characters,
            text_ai_client=self._text_ai_client,
            character_user_memory_service=self._character_user_memory_service,
            character_memory_note_service=self._character_memory_note_service,
            session_objective_note_service=self._session_objective_note_service,
        )
        self._conversation_service = LiveChatConversationService(
            chat_session_service=self._chat_session_service,
            chat_message_service=self._chat_message_service,
            session_state_service=self._session_state_service,
            letter_service=self._letter_service,
            media_service=self._media_service,
            text_ai_client=self._text_ai_client,
            context_provider=self.get_session_context,
            serialize_message=self._serialize_message,
            serialize_state=self._serialize_state,
            character_user_memory_service=self._character_user_memory_service,
            character_memory_note_service=self._character_memory_note_service,
            session_objective_note_service=self._session_objective_note_service,
        )
        self._session_workflow_service = LiveChatSessionWorkflowService(
            chat_session_service=self._chat_session_service,
            chat_message_service=self._chat_message_service,
            session_state_service=self._session_state_service,
            character_service=self._character_service,
            live_chat_room_service=self._live_chat_room_service,
            media_service=self._media_service,
            conversation_service=self._conversation_service,
            serializer=self._serializer,
            context_provider=self.get_session_context,
        )
        self._gift_service = LiveChatGiftService(
            chat_session_service=self._chat_session_service,
            chat_message_service=self._chat_message_service,
            session_state_service=self._session_state_service,
            session_image_service=self._session_image_service,
            asset_service=self._asset_service,
            session_gift_event_service=self._session_gift_event_service,
            letter_service=self._letter_service,
            media_service=self._media_service,
            text_ai_client=self._text_ai_client,
            image_ai_client=self._image_ai_client,
            context_provider=self.get_session_context,
            update_session_memory=self._update_session_memory,
            update_conversation_evaluation=self._update_conversation_evaluation,
            serialize_message=self._serialize_message,
            character_user_memory_service=self._character_user_memory_service,
        )
        self._short_story_service = LiveChatShortStoryService(
            text_ai_client=self._text_ai_client,
            image_ai_client=self._image_ai_client,
            chat_session_service=self._chat_session_service,
            asset_service=self._asset_service,
            session_image_service=self._session_image_service,
            serialize_session_image=self._serialize_session_image,
            context_provider=self.get_session_context,
        )

    def _load_json(self, value):
        return self._serializer.load_json(value)

    def _build_media_url(self, file_path: str | None):
        return self._serializer.build_media_url(file_path)

    def _serialize_asset(self, asset):
        return self._serializer.serialize_asset(asset)

    def _serialize_character(self, character):
        return self._serializer.serialize_character(character)

    def _serialize_session(self, row):
        return self._serializer.serialize_session(row)

    def _serialize_message(self, row):
        return self._serializer.serialize_message(row)

    def _serialize_state(self, row):
        return self._serializer.serialize_state(row)

    def _serialize_session_image(self, row):
        return self._media_service.serialize_session_image(row)

    def _collect_session_reference_assets(self, session_id: int, active_characters: list[dict], *, limit: int = 1):
        return self._media_service.collect_session_reference_assets(session_id, active_characters, limit=limit)

    def _ensure_initial_costume(self, session_id: int):
        return self._media_service.ensure_initial_costume(session_id)

    def _serialize_gift_event(self, row):
        return self._gift_service.serialize_gift_event(row)

    def _selected_character_ids_from_session(self, session) -> list[int]:
        return self._session_workflow_service.selected_character_ids_from_session(session)

    def _select_characters(self, session_id: int):
        return self._session_workflow_service.select_characters(session_id)

    def _analyze_displayed_image(self, file_path: str, *, prompt: str | None = None, source: str = "generated_image"):
        return self._media_service.analyze_displayed_image(file_path, prompt=prompt, source=source)

    def list_sessions(
        self,
        project_id: int,
        owner_user_id: int | None = None,
        include_private_details: bool = True,
        detail_owner_user_id: int | None = None,
        room_id: int | None = None,
    ):
        return self._context_service.list_sessions(
            project_id,
            owner_user_id=owner_user_id,
            include_private_details=include_private_details,
            detail_owner_user_id=detail_owner_user_id,
            room_id=room_id,
        )

    def create_session(self, project_id: int, payload: dict | None = None, owner_user_id: int | None = None):
        return self._session_workflow_service.create_session(project_id, payload, owner_user_id=owner_user_id)

    def create_session_from_room(self, room_id: int, payload: dict | None = None, owner_user_id: int | None = None):
        return self._session_workflow_service.create_session_from_room(room_id, payload, owner_user_id=owner_user_id)

    def _preserve_locked_session_characters(self, session_id: int, payload: dict) -> dict:
        return self._session_workflow_service._preserve_locked_session_characters(session_id, payload)

    def update_session(self, session_id: int, payload: dict | None = None):
        return self._session_workflow_service.update_session(session_id, payload)

    def delete_message(self, session_id: int, message_id: int):
        return self._session_workflow_service.delete_message(session_id, message_id)

    def get_session_context(self, session_id: int):
        return self._context_service.get_session_context(session_id)

    def _update_session_memory(self, session_id: int, context: dict):
        return self._conversation_service.update_session_memory(session_id, context)

    def _update_conversation_evaluation(self, session_id: int, context: dict):
        return self._conversation_service.update_conversation_evaluation(session_id, context)

    def post_message(self, session_id: int, payload: dict | None = None):
        return self._conversation_service.post_message(session_id, payload)

    def generate_player_proxy_message(self, session_id: int, payload: dict | None = None):
        return self._conversation_service.generate_player_proxy_message(session_id, payload)

    def post_idle_character_message(self, session_id: int):
        return self._conversation_service.post_idle_character_message(session_id)

    def extract_state(self, session_id: int):
        return self._session_workflow_service.extract_state(session_id)

    def generate_image(self, session_id: int, payload: dict | None = None):
        return self._media_service.generate_image(session_id, payload)

    def register_uploaded_image(self, session_id: int, asset_id: int, payload: dict | None = None):
        return self._media_service.register_uploaded_image(session_id, asset_id, payload)

    def execute_scene_choice(self, session_id: int, choice_id: str, payload: dict | None = None):
        return self._conversation_service.execute_scene_choice(session_id, choice_id, payload)

    def move_to_location(self, session_id: int, location_id: int, payload: dict | None = None):
        return self._conversation_service.move_to_location(session_id, location_id, payload)

    def select_location_service(self, session_id: int, service_id: int, payload: dict | None = None):
        return self._conversation_service.select_location_service(session_id, service_id, payload)

    def enter_lccd_room(self, session_id: int, payload: dict | None = None):
        return self._conversation_service.enter_lccd_room(session_id, payload)

    def generate_lccd_photo_shoot(self, session_id: int, payload: dict | None = None):
        return self._conversation_service.generate_lccd_photo_shoot(session_id, payload)

    def list_costumes(self, session_id: int):
        return self._media_service.list_costumes(session_id)

    def select_costume(self, session_id: int, session_image_id: int):
        return self._media_service.select_costume(session_id, session_image_id)

    def list_closet_outfits(self, session_id: int):
        return self._media_service.list_closet_outfits(session_id)

    def select_closet_outfit(self, session_id: int, outfit_id: int):
        return self._media_service.select_closet_outfit(session_id, outfit_id)

    def create_scene_from_selected_costume(self, session_id: int, *, reason: str | None = None):
        return self._media_service.create_scene_from_selected_costume(session_id, reason=reason)

    def register_uploaded_costume(self, session_id: int, asset_id: int, payload: dict | None = None):
        return self._media_service.register_uploaded_costume(session_id, asset_id, payload)

    def delete_costume(self, session_id: int, session_image_id: int):
        return self._media_service.delete_costume(session_id, session_image_id)

    def generate_costume(self, session_id: int, payload: dict | None = None):
        return self._media_service.generate_costume(session_id, payload)

    def select_image(self, session_image_id: int, *, update_observation: bool = True, session_id: int | None = None):
        return self._media_service.select_image(
            session_image_id,
            update_observation=update_observation,
            session_id=session_id,
        )

    def set_reference_image(self, session_id: int, session_image_id: int, is_reference: bool):
        return self._media_service.set_reference_image(session_id, session_image_id, is_reference)

    def upload_gift(self, session_id: int, asset_id: int, payload: dict | None = None):
        return self._gift_service.upload_gift(session_id, asset_id, payload)

    def analyze_player_reaction(self, session_id: int, upload_file):
        return self._player_reaction_service.analyze_frame(session_id, upload_file)

    def generate_short_story(self, session_id: int, payload: dict | None = None):
        return self._short_story_service.generate_short_story(session_id, payload)

    def save_short_story(self, session_id: int, payload: dict | None = None):
        return self._short_story_service.save_short_story(session_id, payload)
