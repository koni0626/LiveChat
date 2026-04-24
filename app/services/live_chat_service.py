from __future__ import annotations

import os

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..utils import json_util
from . import live_chat_image_support as image_support
from . import live_chat_prompt_support as prompt_support
from . import live_chat_text_support as text_support
from .asset_service import AssetService
from .character_service import CharacterService
from .chat_message_service import ChatMessageService
from .chat_session_service import ChatSessionService
from .project_service import ProjectService
from .session_image_service import SessionImageService
from .session_state_service import SessionStateService
from .story_outline_service import StoryOutlineService
from .world_service import WorldService


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
        story_outline_service: StoryOutlineService | None = None,
        world_service: WorldService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._chat_session_service = chat_session_service or ChatSessionService()
        self._chat_message_service = chat_message_service or ChatMessageService()
        self._session_state_service = session_state_service or SessionStateService()
        self._session_image_service = session_image_service or SessionImageService()
        self._project_service = project_service or ProjectService()
        self._character_service = character_service or CharacterService()
        self._asset_service = asset_service or AssetService()
        self._story_outline_service = story_outline_service or StoryOutlineService()
        self._world_service = world_service or WorldService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()

    def _load_json(self, value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return json_util.loads(stripped)
        except Exception:
            return value

    def _build_media_url(self, file_path: str | None):
        if not file_path:
            return None
        try:
            storage_root = current_app.config.get("STORAGE_ROOT")
        except RuntimeError:
            storage_root = None
        if not storage_root:
            return None
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        if not normalized_path.startswith(normalized_root):
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"

    def _serialize_asset(self, asset):
        if asset is None:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "file_path": asset.file_path,
            "mime_type": asset.mime_type,
            "file_size": asset.file_size,
            "width": asset.width,
            "height": asset.height,
            "media_url": self._build_media_url(asset.file_path),
        }

    def _serialize_character(self, character):
        base_asset = self._asset_service.get_asset(character.base_asset_id) if getattr(character, "base_asset_id", None) else None
        return {
            "id": character.id,
            "name": character.name,
            "role": character.role,
            "first_person": character.first_person,
            "second_person": character.second_person,
            "personality": character.personality,
            "speech_style": character.speech_style,
            "speech_sample": character.speech_sample,
            "ng_rules": character.ng_rules,
            "appearance_summary": character.appearance_summary,
            "is_guide": bool(character.is_guide),
            "base_asset": self._serialize_asset(base_asset),
        }

    def _serialize_session(self, row):
        return {
            "id": row.id,
            "project_id": row.project_id,
            "title": row.title,
            "session_type": row.session_type,
            "status": row.status,
            "active_image_id": row.active_image_id,
            "player_name": row.player_name,
            "settings_json": self._load_json(row.settings_json),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def _serialize_message(self, row):
        return {
            "id": row.id,
            "session_id": row.session_id,
            "sender_type": row.sender_type,
            "speaker_name": row.speaker_name,
            "message_text": row.message_text,
            "order_no": row.order_no,
            "message_role": row.message_role,
            "state_snapshot_json": self._load_json(row.state_snapshot_json),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
        }

    def _serialize_state(self, row):
        if row is None:
            return {
                "state_json": {},
                "narration_note": None,
                "visual_prompt_text": None,
            }
        return {
            "id": row.id,
            "session_id": row.session_id,
            "state_json": self._load_json(row.state_json) or {},
            "narration_note": row.narration_note,
            "visual_prompt_text": row.visual_prompt_text,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def _serialize_session_image(self, row):
        asset = self._asset_service.get_asset(row.asset_id)
        return {
            "id": row.id,
            "session_id": row.session_id,
            "asset_id": row.asset_id,
            "image_type": row.image_type,
            "prompt_text": row.prompt_text,
            "state_json": self._load_json(row.state_json),
            "quality": row.quality,
            "size": row.size,
            "is_selected": bool(row.is_selected),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "asset": self._serialize_asset(asset),
        }

    def _select_characters(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return []
        all_characters = self._character_service.list_characters(session.project_id)
        return [self._serialize_character(character) for character in all_characters]

    def list_sessions(self, project_id: int):
        items = self._chat_session_service.list_sessions(project_id)
        serialized = []
        for item in items:
            messages = self._chat_message_service.list_messages(item.id)
            session_characters = self._select_characters(item.id)
            serialized.append(
                {
                    **self._serialize_session(item),
                    "message_count": len(messages),
                    "last_message_text": messages[-1].message_text if messages else None,
                    "characters": session_characters,
                }
            )
        return serialized

    def create_session(self, project_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.create_session(project_id, payload)
        if not session:
            return None
        self._session_state_service.upsert_state(session.id, {"state_json": {}})
        return self.get_session_context(session.id)

    def update_session(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.update_session(session_id, payload)
        if not session:
            return None
        return self.get_session_context(session_id)

    def delete_message(self, session_id: int, message_id: int):
        row = self._chat_message_service.delete_message(message_id)
        if not row or row.session_id != session_id:
            return None
        context = self.get_session_context(session_id)
        self._update_conversation_evaluation(session_id, context)
        return self.get_session_context(session_id)

    def get_session_context(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        project = self._project_service.get_project(session.project_id)
        state = self._session_state_service.get_state(session_id)
        messages = self._chat_message_service.list_messages(session_id)
        images = self._session_image_service.list_session_images(session_id)
        selected_image = next((item for item in images if item.is_selected), None)
        characters = self._select_characters(session_id)
        story_outline = self._story_outline_service.get_outline(session.project_id)
        world = self._world_service.get_world(session.project_id)
        if not messages and characters:
            opening_context = {
                "project": {
                    "id": project.id if project else session.project_id,
                    "title": project.title if project else None,
                    "genre": project.genre if project else None,
                },
                "story_outline": {
                    "protagonist_name": getattr(story_outline, "protagonist_name", None) if story_outline else None,
                    "premise": getattr(story_outline, "premise", None) if story_outline else None,
                },
                "world": {
                    "name": getattr(world, "name", None) if world else None,
                    "overview": getattr(world, "overview", None) if world else None,
                    "tone": getattr(world, "tone", None) if world else None,
                },
                "session": self._serialize_session(session),
                "messages": [],
                "state": self._serialize_state(state),
                "characters": characters,
            }
            self._create_opening_message(session, opening_context)
            messages = self._chat_message_service.list_messages(session_id)
        return {
            "project": {
                "id": project.id if project else session.project_id,
                "title": project.title if project else None,
                "genre": project.genre if project else None,
            },
            "story_outline": {
                "protagonist_name": getattr(story_outline, "protagonist_name", None) if story_outline else None,
                "premise": getattr(story_outline, "premise", None) if story_outline else None,
            },
            "world": {
                "name": getattr(world, "name", None) if world else None,
                "overview": getattr(world, "overview", None) if world else None,
                "tone": getattr(world, "tone", None) if world else None,
            },
            "session": self._serialize_session(session),
            "messages": [self._serialize_message(item) for item in messages],
            "state": self._serialize_state(state),
            "characters": characters,
            "images": [self._serialize_session_image(item) for item in images],
            "selected_image": self._serialize_session_image(selected_image) if selected_image else None,
        }

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

    def _update_line_visual_note(self, session_id: int, context: dict):
        latest_character_message = None
        for message in reversed(context["messages"]):
            if message.get("sender_type") == "character":
                latest_character_message = message
                break
        if not latest_character_message:
            return None
        note = text_support.generate_line_visual_note(
            self._text_ai_client,
            context,
            latest_character_message.get("speaker_name") or "character",
            latest_character_message.get("message_text") or "",
        )
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json["line_visual_note"] = note
        if note.get("location"):
            state_json["location"] = note["location"]
        if note.get("background"):
            state_json["background"] = note["background"]
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _update_session_memory(self, session_id: int, context: dict):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json["session_memory"] = prompt_support.build_session_memory(context["messages"], state_json)
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _update_conversation_evaluation(self, session_id: int, context: dict):
        evaluation = text_support.generate_conversation_evaluation(self._text_ai_client, context)
        if evaluation is None:
            return None
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        state_json["conversation_evaluation"] = evaluation
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _update_conversation_director(self, session_id: int, context: dict, user_message_text: str):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        director = text_support.generate_conversation_director(self._text_ai_client, context, user_message_text)
        relationship_state = dict(state_json.get("relationship_state") or {})
        relationship_state = prompt_support.apply_director_relationship_update(relationship_state, context, director)
        state_json["conversation_director"] = director
        state_json["relationship_state"] = relationship_state
        return self._session_state_service.upsert_state(session_id, {"state_json": state_json})

    def _update_scene_progression(self, session_id: int, context: dict, user_message_text: str):
        state_row = self._session_state_service.get_state(session_id)
        state_json = self._load_json(getattr(state_row, "state_json", None)) or {}
        progression = text_support.generate_scene_progression(self._text_ai_client, context, user_message_text)
        state_json["scene_progression"] = progression
        if progression.get("location"):
            state_json["location"] = progression["location"]
        if progression.get("background"):
            state_json["background"] = progression["background"]
        if progression.get("focus_summary"):
            state_json["focus_summary"] = progression["focus_summary"]
        return self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "narration_note": progression.get("focus_summary"),
            },
        )

    def post_message(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        message_text = str(payload.get("message_text") or "").strip() or "話を進めて"
        user_message = self._chat_message_service.create_message(
            session_id,
            {
                "sender_type": payload.get("sender_type") or "user",
                "speaker_name": payload.get("speaker_name") or session.player_name or "プレイヤー",
                "message_text": message_text,
                "message_role": "player",
            },
        )
        created = [self._serialize_message(user_message)]
        context = self.get_session_context(session_id)
        self._update_scene_progression(session_id, context, user_message.message_text)
        context = self.get_session_context(session_id)
        self._update_conversation_director(session_id, context, user_message.message_text)
        context = self.get_session_context(session_id)
        auto_reply = str(payload.get("auto_reply", "true")).lower() not in {"0", "false", "no", "off"}
        if auto_reply:
            reply = text_support.generate_reply(self._text_ai_client, context, user_message.message_text)
            assistant_message = self._chat_message_service.create_message(
                session_id,
                {
                    "sender_type": "character",
                    "speaker_name": reply["speaker_name"],
                    "message_text": reply["message_text"],
                    "message_role": "assistant",
                },
            )
            created.append(self._serialize_message(assistant_message))
        updated_context = self.get_session_context(session_id)
        self._update_line_visual_note(session_id, updated_context)
        updated_context = self.get_session_context(session_id)
        self._update_session_memory(session_id, updated_context)
        updated_context = self.get_session_context(session_id)
        self._update_conversation_evaluation(session_id, updated_context)
        updated_context = self.get_session_context(session_id)
        state = self._session_state_service.extract_state(
            session=session,
            messages=updated_context["messages"],
            characters=updated_context["characters"],
        )
        return {
            "messages": created,
            "state": self._serialize_state(state),
            "session": updated_context["session"],
        }

    def extract_state(self, session_id: int):
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        context = self.get_session_context(session_id)
        state = self._session_state_service.extract_state(
            session=session,
            messages=context["messages"],
            characters=context["characters"],
        )
        return self._serialize_state(state)

    def generate_image(self, session_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session = self._chat_session_service.get_session(session_id)
        if not session:
            return None
        context = self.get_session_context(session_id)
        state = context["state"]
        state_json = dict(state.get("state_json") or {})
        conversation_prompt = image_support.generate_japanese_conversation_image_prompt(self._text_ai_client, context, state)
        state_json["conversation_image_prompt"] = conversation_prompt
        reuse_existing_prompt = str(payload.get("use_existing_prompt") or "").lower() in {"1", "true", "yes", "on"}
        prompt = str(payload.get("prompt_text") or "").strip() if reuse_existing_prompt else ""
        if not prompt:
            prompt = str(conversation_prompt.get("prompt_ja") or "").strip()
        prompt = prompt_support.normalize_first_person_visual_prompt(prompt)
        visual_state = prompt_support.build_visual_state(context, state, prompt=prompt)
        state_json["visual_state"] = visual_state

        active_characters = image_support.resolve_active_characters(context, state_json, conversation_prompt)
        reference_paths, reference_asset_ids = image_support.collect_reference_assets(active_characters, limit=2)
        result = self._image_ai_client.generate_image(
            prompt,
            size=payload.get("size") or "1536x1024",
            quality=payload.get("quality") or "low",
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("image generation response did not include image_base64")
        try:
            storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        except RuntimeError:
            storage_root = os.path.join(os.getcwd(), "storage")
        file_name, file_path, file_size = image_support.store_generated_image(
            storage_root=storage_root,
            project_id=session.project_id,
            session_id=session.id,
            image_base64=image_base64,
        )
        asset = self._asset_service.create_asset(
            session.project_id,
            {
                "asset_type": "generated_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "live_chat",
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_asset_ids,
                    }
                ),
            },
        )
        session_image = self._session_image_service.create_session_image(
            session_id,
            {
                "asset_id": asset.id,
                "image_type": payload.get("image_type") or "live_scene",
                "prompt_text": prompt,
                "state_json": state.get("state_json") or {},
                "quality": payload.get("quality") or "low",
                "size": payload.get("size") or "1536x1024",
                "is_selected": 1,
            },
        )
        self.select_image(session_image.id)
        self._session_state_service.upsert_state(
            session_id,
            {
                "state_json": state_json,
                "visual_prompt_text": result.get("revised_prompt") or prompt,
            },
        )
        return self._serialize_session_image(session_image)

    def register_uploaded_image(self, session_id: int, asset_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        session_image = self._session_image_service.create_session_image(
            session_id,
            {
                "asset_id": asset_id,
                "image_type": payload.get("image_type") or "live_scene",
                "prompt_text": payload.get("prompt_text"),
                "state_json": payload.get("state_json"),
                "quality": payload.get("quality") or "external",
                "size": payload.get("size") or "uploaded",
                "is_selected": 1 if payload.get("is_selected", True) else 0,
            },
        )
        if payload.get("is_selected", True):
            self.select_image(session_image.id)
        return self._serialize_session_image(session_image)

    def select_image(self, session_image_id: int):
        row = self._session_image_service.select_session_image(session_image_id)
        if not row:
            return None
        self._chat_session_service.update_session(row.session_id, {"active_image_id": row.asset_id})
        return self._serialize_session_image(row)
