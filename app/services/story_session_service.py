from __future__ import annotations

from datetime import datetime
import base64
import binascii
import os
import threading

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..extensions import db
from ..repositories.feed_repository import FeedRepository
from ..repositories.story_image_repository import StoryImageRepository
from ..repositories.story_message_repository import StoryMessageRepository
from ..repositories.story_session_repository import StorySessionRepository
from ..utils import json_util
from .asset_service import AssetService
from .character_service import CharacterService
from .closet_service import ClosetService
from .letter_service import LetterService
from .project_service import ProjectService
from . import live_chat_prompt_support as prompt_support
from . import live_chat_text_support as text_support
from .story_dice_service import StoryDiceService
from .story_service import StoryService
from .story_state_service import StoryStateService
from .user_setting_service import UserSettingService
from .world_map_service import WorldMapService


class StorySessionService:
    def __init__(
        self,
        repository: StorySessionRepository | None = None,
        message_repository: StoryMessageRepository | None = None,
        image_repository: StoryImageRepository | None = None,
        story_service: StoryService | None = None,
        state_service: StoryStateService | None = None,
        dice_service: StoryDiceService | None = None,
        asset_service: AssetService | None = None,
        character_service: CharacterService | None = None,
        project_service: ProjectService | None = None,
        letter_service: LetterService | None = None,
        feed_repository: FeedRepository | None = None,
        user_setting_service: UserSettingService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
        world_map_service: WorldMapService | None = None,
    ):
        self._repo = repository or StorySessionRepository()
        self._message_repo = message_repository or StoryMessageRepository()
        self._image_repo = image_repository or StoryImageRepository()
        self._story_service = story_service or StoryService()
        self._state_service = state_service or StoryStateService()
        self._dice_service = dice_service or StoryDiceService()
        self._asset_service = asset_service or AssetService()
        self._character_service = character_service or CharacterService()
        self._project_service = project_service or ProjectService()
        self._letter_service = letter_service or LetterService()
        self._feed_repository = feed_repository or FeedRepository()
        self._user_setting_service = user_setting_service or UserSettingService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._world_map_service = world_map_service or WorldMapService()
        self._closet_service = ClosetService()

    def list_sessions(self, project_id: int, *, owner_user_id: int | None = None):
        return self._repo.list_by_project(project_id, owner_user_id=owner_user_id)

    def list_sessions_by_story(self, story_id: int, *, owner_user_id: int | None = None):
        return self._repo.list_by_story(story_id, owner_user_id=owner_user_id)

    def get_session(self, session_id: int):
        return self._repo.get(session_id)

    def serialize_session(self, row, *, include_state: bool = False, include_messages: bool = False):
        if not row:
            return None
        story = self._story_service.get_story(row.story_id)
        payload = {
            "id": row.id,
            "project_id": row.project_id,
            "story_id": row.story_id,
            "owner_user_id": row.owner_user_id,
            "title": row.title,
            "status": row.status,
            "privacy_status": row.privacy_status,
            "player_name": row.player_name,
            "active_image_id": row.active_image_id,
            "active_image": self._serialize_asset(self._asset_service.get_asset(row.active_image_id)) if row.active_image_id else None,
            "story_snapshot_json": self._state_service.load_json(row.story_snapshot_json),
            "settings_json": self._state_service.load_json(row.settings_json),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
            "story": self._story_service.serialize_story(story) if story else None,
        }
        if include_state:
            payload["state"] = self._state_service.serialize_state(self._state_service.get_state(row.id))
        if include_messages:
            payload["messages"] = [self.serialize_message(message) for message in self._message_repo.list_by_session(row.id)]
            payload["images"] = [self.serialize_image(image) for image in self._image_repo.list_by_session(row.id)]
            costumes = self.list_costumes(row.id)
            payload["costumes"] = costumes
            payload["selected_costume"] = next((item for item in costumes if item.get("is_selected")), None)
        return payload

    def serialize_sessions(self, rows):
        return [self.serialize_session(row) for row in rows]

    def serialize_message(self, row):
        if not row:
            return None
        return {
            "id": row.id,
            "session_id": row.session_id,
            "sender_type": row.sender_type,
            "speaker_name": row.speaker_name,
            "message_text": row.message_text,
            "message_type": row.message_type,
            "order_no": row.order_no,
            "metadata_json": self._state_service.load_json(row.metadata_json),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def serialize_image(self, row):
        if not row:
            return None
        asset = self._asset_service.get_asset(row.asset_id)
        return {
            "id": row.id,
            "session_id": row.session_id,
            "asset_id": row.asset_id,
            "source_message_id": row.source_message_id,
            "visual_type": row.visual_type,
            "subject": row.subject,
            "prompt_text": row.prompt_text,
            "reference_asset_ids_json": self._state_service.load_json(row.reference_asset_ids_json),
            "metadata_json": self._state_service.load_json(row.metadata_json),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "asset": self._serialize_asset(asset),
        }

    def create_session_from_story(self, story_id: int, payload: dict | None = None, *, owner_user_id: int):
        payload = dict(payload or {})
        story = self._story_service.get_story(story_id)
        if not story:
            return None
        if not owner_user_id:
            raise ValueError("owner_user_id is required")
        player_name = str(payload.get("player_name") or "").strip()
        if not player_name:
            raise ValueError("player_name is required")
        title = str(payload.get("title") or "").strip() or f"{story.title} {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        snapshot = self._story_service.build_story_snapshot(story)
        session = self._repo.create(
            {
                "project_id": story.project_id,
                "story_id": story.id,
                "owner_user_id": owner_user_id,
                "title": title,
                "status": payload.get("status") or "active",
                "privacy_status": payload.get("privacy_status") or "private",
                "player_name": player_name,
                "story_snapshot_json": json_util.dumps(snapshot),
                "settings_json": json_util.dumps(payload.get("settings_json") or {}),
            }
        )
        initial_state = self._state_service.load_json(story.initial_state_json)
        if not initial_state:
            initial_state = self._state_service.default_state(story.story_mode)
        self._state_service.initialize_state(session.id, initial_state)
        opening_context = self._build_generation_context(session)
        self._create_opening_gm_message(session, opening_context)
        initial_image = None
        image_generation_error = None
        if payload.get("generate_initial_image", True):
            try:
                initial_image = self.generate_scene_image(
                    session.id,
                    {
                        **({"quality": payload.get("quality")} if payload.get("quality") else {}),
                        **({"size": payload.get("size")} if payload.get("size") else {}),
                        "visual_type": "opening",
                        "subject": story.title,
                    },
                )
            except Exception as exc:
                image_generation_error = str(exc)
        serialized = self.serialize_session(self.get_session(session.id), include_state=True, include_messages=True)
        serialized["initial_image"] = initial_image
        if image_generation_error:
            serialized["image_generation_error"] = image_generation_error
        return serialized

    def _create_opening_gm_message(self, session, context: dict):
        turn_plan = self._story_turn_plan(context)
        choices = self._fallback_choices(context, turn_plan)
        story = context.get("story") or {}
        state = context.get("state") or {}
        game_state = state.get("game_state") if isinstance(state.get("game_state"), dict) else {}
        goal = str(context.get("current_goal") or story.get("description") or "物語の目的").strip()
        location = str(game_state.get("location") or "物語の入口").strip()
        character_name = self._main_character_display_name(context)
        story_title = str(story.get("title") or session.title).strip()
        message_text = (
            f"セッション「{story_title}」を開始します。\n"
            f"現在地は「{location}」。{session.player_name}と{character_name}は、"
            f"目的「{goal}」へ向かう最初の場面に立っています。\n"
            "GMとして状況を提示します。まず、最初の行動を選んでください。"
        )
        patch = {
            "choice_state": {"last_choices": choices},
            "goal_state": {
                "max_turns": turn_plan["max_turns"],
                "current_turn": 0,
                "current_phase": "opening",
                "current_phase_label": "導入・目的提示",
                "current_goal": goal,
                "session_status": "active",
            },
            "visual_state": {
                "active_visual_type": "opening",
                "active_subject": story_title,
            },
        }
        self._state_service.apply_patch(session.id, patch)
        self.create_message(
            session.id,
            {
                "sender_type": "gm",
                "speaker_name": "GM",
                "message_text": message_text,
                "message_type": "narration",
                "metadata_json": {
                    "source": "session_start",
                    "next_choices": choices,
                },
            },
        )

    def create_message(self, session_id: int, payload: dict):
        order_no = self._message_repo.get_max_order_no(session_id) + 1
        metadata_json = payload.get("metadata_json")
        if isinstance(metadata_json, (dict, list)):
            metadata_json = json_util.dumps(metadata_json)
        return self._message_repo.create(
            {
                "session_id": session_id,
                "sender_type": payload["sender_type"],
                "speaker_name": payload.get("speaker_name"),
                "message_text": payload["message_text"],
                "message_type": payload.get("message_type") or "dialogue",
                "order_no": order_no,
                "metadata_json": metadata_json,
            }
        )

    def post_user_message(self, session_id: int, message_text: str):
        session = self.get_session(session_id)
        if not session:
            return None
        text = str(message_text or "").strip()
        if not text:
            raise ValueError("message_text is required")
        user_message = self.create_message(
            session_id,
            {
                "sender_type": "user",
                "speaker_name": session.player_name,
                "message_text": text,
                "message_type": "dialogue",
            },
        )
        context = self._build_generation_context(session)
        gm_result = self._generate_gm_result(context, text)
        state_row = self._state_service.apply_patch(session_id, gm_result.get("state_patch"))
        updated_context = self._build_generation_context(session)
        updated_context["gm_result"] = gm_result
        scene_messages = self._create_scene_messages(session, gm_result, updated_context, text)
        letter_scheduled = self._schedule_clear_letter_if_needed(session.id, state_row)
        return {
            "user_message": self.serialize_message(user_message),
            "gm_message": self.serialize_message(scene_messages[0]) if scene_messages else None,
            "character_message": self.serialize_message(scene_messages[-1]) if scene_messages else None,
            "scene_messages": [self.serialize_message(message) for message in scene_messages],
            "state": self._state_service.serialize_state(state_row),
            "next_choices": gm_result.get("next_choices") or [],
            "letter_scheduled": letter_scheduled,
        }

    def execute_choice(self, session_id: int, choice_id: str, *, generate_image: bool = False):
        session = self.get_session(session_id)
        if not session:
            return None
        state = self._state_service.serialize_state(self._state_service.get_state(session_id)) or {}
        choices = ((state.get("state_json") or {}).get("choice_state") or {}).get("last_choices") or []
        choice = next((item for item in choices if str(item.get("id")) == str(choice_id)), None)
        if not choice:
            raise ValueError("choice is not available")
        label = str(choice.get("label") or "").strip()
        if not label:
            raise ValueError("choice label is empty")
        result = self.post_user_message(session_id, label)
        if generate_image and result:
            try:
                result["generated_image"] = self.generate_scene_image(
                    session_id,
                    {
                        "visual_type": "choice_result",
                        "subject": label,
                    },
                )
            except Exception as exc:
                result["image_generation_error"] = str(exc)
        return result

    def _schedule_clear_letter_if_needed(self, session_id: int, state_row) -> bool:
        state = self._state_service.load_json(getattr(state_row, "state_json", None), fallback={})
        goal_state = state.get("goal_state") if isinstance(state.get("goal_state"), dict) else {}
        if str(goal_state.get("session_status") or "").strip() not in {"cleared", "failed", "bittersweet_end"}:
            return False
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            session = self.get_session(session_id)
            if session:
                self._generate_clear_letter(session)
            return False

        def worker():
            with app.app_context():
                try:
                    session = self.get_session(session_id)
                    if session:
                        self._generate_clear_letter(session)
                except Exception:
                    app.logger.exception("story clear letter generation failed")
                finally:
                    db.session.remove()

        threading.Thread(target=worker, name=f"story-clear-letter-{session_id}", daemon=True).start()
        return True

    def _generate_clear_letter(self, session):
        context = self._build_generation_context(session)
        messages = [self.serialize_message(message) for message in self._message_repo.list_by_session(session.id)]
        character = context.get("character") or {}
        story = context.get("story") or {}
        context["messages"] = messages
        context["recent_messages"] = messages[-16:]
        context["characters"] = [character] if character else []
        selected_costume = self._selected_costume_image(session.id)
        if selected_costume:
            context["letter_reference_asset_ids"] = [selected_costume.asset_id]
        elif ((story.get("default_outfit") or {}).get("asset") or {}).get("id"):
            context["letter_reference_asset_ids"] = [((story.get("default_outfit") or {}).get("asset") or {}).get("id")]
        elif character.get("base_asset_id"):
            context["letter_reference_asset_ids"] = [character.get("base_asset_id")]
        context["room"] = {
            "character_id": character.get("id"),
            "conversation_objective": context.get("current_goal") or story.get("description") or story.get("title") or "",
        }
        return self._letter_service.generate_for_story_context(session, context, trigger_type="story_clear")

    def roll_dice(self, session_id: int, payload: dict | None = None):
        session = self.get_session(session_id)
        if not session:
            return None
        payload = dict(payload or {})
        formula = str(payload.get("formula") or "1d20").strip()
        target = payload.get("target")
        if target is not None:
            try:
                target = int(target)
            except (TypeError, ValueError):
                raise ValueError("target must be an integer")
        roll = self._dice_service.roll(
            session_id,
            formula,
            target=target,
            reason=str(payload.get("reason") or "").strip() or None,
            metadata={"source": "story_session_roll"},
        )
        message = self.create_message(
            session_id,
            {
                "sender_type": "gm",
                "speaker_name": "GM",
                "message_text": self._format_roll_message(roll),
                "message_type": "dice_result",
                "metadata_json": {"roll": roll},
            },
        )
        return {"roll": roll, "message": self.serialize_message(message)}

    def generate_character_message(self, session_id: int, payload: dict | None = None):
        session = self.get_session(session_id)
        if not session:
            return None
        payload = dict(payload or {})
        trigger_text = str(payload.get("trigger_text") or "").strip() or "現在の状況に反応する"
        context = self._build_generation_context(session)
        context["gm_result"] = {
            "narration": trigger_text,
            "gm_event": {"source": "manual_auto_line"},
        }
        message = self.create_message(
            session_id,
            {
                "sender_type": "character",
                "speaker_name": self._main_character_name(session),
                "message_text": self._generate_character_line(context, trigger_text),
                "message_type": "dialogue",
                "metadata_json": {"source": "manual_auto_line", "trigger_text": trigger_text},
            },
        )
        return {"message": self.serialize_message(message)}

    def generate_player_draft(self, session_id: int, payload: dict | None = None):
        session = self.get_session(session_id)
        if not session:
            return None
        payload = dict(payload or {})
        context = self._build_generation_context(session)
        prompt = self._build_player_draft_prompt(context, payload)
        try:
            result = self._text_ai_client.generate_text(prompt, temperature=0.8, response_format={"type": "json_object"})
            parsed = self._text_ai_client._try_parse_json(result.get("text"))
            if isinstance(parsed, dict):
                text = str(parsed.get("message_text") or "").strip()
                if text:
                    return {"message_text": self._normalize_player_text(text, context)}
        except Exception:
            pass
        choices = ((context.get("state") or {}).get("choice_state") or {}).get("last_choices") or []
        fallback = str((choices[0] or {}).get("label") or "周囲を調べる").strip() if choices else "周囲を調べる"
        return {"message_text": self._normalize_player_text(fallback, context)}

    def generate_scene_image(self, session_id: int, payload: dict | None = None):
        session = self.get_session(session_id)
        if not session:
            return None
        payload = dict(payload or {})
        context = self._build_generation_context(session)
        image_options = self._scene_image_options(session, payload)
        prompt = str(payload.get("prompt_text") or "").strip() or self._generate_scene_image_prompt(context)
        visual_context = self._build_live_chat_visual_context(session, context)
        reference_paths, reference_asset_ids = self._collect_reference_assets(context)
        outfit = self._default_outfit_for_context(context)
        prompt, prompt_metadata = self._polish_scene_image_prompt(prompt, visual_context, payload)
        outfit_lines = self._closet_service.outfit_prompt_lines(outfit)
        if outfit_lines:
            prompt = "\n".join([prompt, *outfit_lines])
        prompt = self._apply_costume_reference_guardrails(prompt, reference_asset_ids)
        prompt = self._apply_first_person_game_cg_guardrails(prompt)
        prompt_metadata["costume_reference_asset_ids"] = reference_asset_ids
        prompt_metadata["first_person_game_cg"] = True
        result = self._image_ai_client.generate_image(
            prompt,
            size=image_options["size"],
            quality=image_options["quality"],
            model=image_options.get("model"),
            provider=image_options.get("provider"),
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_image(session, image_base64)
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
                        "source": "story_session",
                        "session_id": session.id,
                        "story_id": session.story_id,
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_asset_ids,
                        "costume_reference_asset_ids": reference_asset_ids,
                        "quality": image_options["quality"],
                        "size": image_options["size"],
                        "prompt_pipeline": prompt_metadata,
                    }
                ),
            },
        )
        image = self._image_repo.create(
            {
                "session_id": session.id,
                "asset_id": asset.id,
                "source_message_id": payload.get("source_message_id"),
                "visual_type": payload.get("visual_type") or self._detect_visual_type(context),
                "subject": payload.get("subject") or self._detect_visual_subject(context),
                "prompt_text": result.get("revised_prompt") or prompt,
                "reference_asset_ids_json": json_util.dumps(reference_asset_ids),
                "metadata_json": json_util.dumps(
                    {
                        "source": "story_session_generate_scene_image",
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "quality": image_options["quality"],
                        "size": image_options["size"],
                        "reference_asset_ids": reference_asset_ids,
                        "prompt_pipeline": prompt_metadata,
                    }
                ),
            }
        )
        self._repo.update(session.id, {"active_image_id": asset.id})
        state_row = self._state_service.get_state(session.id)
        state_json = self._state_service.load_json(state_row.state_json if state_row else None, fallback=self._state_service.default_state())
        visual_state = state_json.setdefault("visual_state", {})
        visual_state["active_image_id"] = asset.id
        visual_state["active_visual_type"] = image.visual_type
        visual_state["active_subject"] = image.subject or ""
        visual_state["last_image_prompt"] = result.get("revised_prompt") or prompt
        state_json["story_scene_image_prompt"] = {
            "prompt_ja": prompt,
            "source": "story_session",
            "pipeline": prompt_metadata,
        }
        if (prompt_metadata.get("safety_rewrite") or {}).get("changed"):
            state_json["image_prompt_safety_rewrite"] = prompt_metadata.get("safety_rewrite")
        self._state_service.upsert_state(session.id, state_json)
        return self.serialize_image(image)

    def list_costumes(self, session_id: int):
        self.ensure_initial_costume(session_id)
        state_row = self._state_service.get_state(session_id)
        state_json = self._state_service.load_json(state_row.state_json if state_row else None, fallback=self._state_service.default_state())
        visual_state = state_json.get("visual_state") or {}
        selected_id = visual_state.get("selected_costume_image_id")
        selected_asset_id = visual_state.get("selected_costume_asset_id")
        rows = self._image_repo.list_costumes_for_session_library(session_id)
        seen_asset_ids = set()
        serialized = []
        for row in rows:
            if row.asset_id in seen_asset_ids:
                continue
            seen_asset_ids.add(row.asset_id)
            data = self.serialize_image(row)
            data["image_type"] = row.visual_type
            data["is_shared"] = row.session_id != session_id
            data["is_selected"] = bool(
                (selected_id and int(row.id) == int(selected_id))
                or (selected_asset_id and int(row.asset_id) == int(selected_asset_id))
            )
            serialized.append(data)
        if serialized and not any(item.get("is_selected") for item in serialized):
            serialized[0]["is_selected"] = True
            self.select_costume(session_id, serialized[0]["id"])
        return serialized

    def ensure_initial_costume(self, session_id: int):
        session = self.get_session(session_id)
        if not session:
            return None
        story = self._story_service.get_story(session.story_id)
        if not story:
            return None
        character = self._character_service.get_character(story.character_id)
        asset_id = self._initial_costume_asset_id(story, character)
        selected = self._selected_costume_image(session_id)
        if selected and selected.visual_type == "costume_reference":
            return self.serialize_image(selected)
        if selected and selected.visual_type == "costume_initial" and (not asset_id or int(selected.asset_id) == int(asset_id)):
            return self.serialize_image(selected)
        existing = [
            row for row in self._image_repo.list_costumes_for_session_library(session_id)
            if row.session_id == session_id and row.visual_type == "costume_initial"
        ]
        if asset_id:
            matching = next((row for row in existing if int(row.asset_id) == int(asset_id)), None)
            if matching:
                self.select_costume(session_id, matching.id)
                return self.serialize_image(matching)
        elif existing:
            return self.serialize_image(existing[0])
        if not asset_id:
            return None
        row = self._image_repo.create(
            {
                "session_id": session_id,
                "asset_id": asset_id,
                "visual_type": "costume_initial",
                "subject": "初期衣装",
                "prompt_text": "キャラクター設定の基準画像",
                "reference_asset_ids_json": json_util.dumps([asset_id]),
                "metadata_json": json_util.dumps({"source": "story_costume_initial", "story_id": session.story_id}),
            }
        )
        self.select_costume(session_id, row.id)
        return self.serialize_image(row)

    def _initial_costume_asset_id(self, story, character):
        outfit_id = getattr(story, "default_outfit_id", None)
        if outfit_id and character:
            outfit = self._closet_service.resolve_outfit(character.id, outfit_id)
            if outfit and getattr(outfit, "asset_id", None):
                return int(outfit.asset_id)
        asset_id = (
            getattr(character, "base_asset_id", None)
            or getattr(story, "main_character_reference_asset_id", None)
        )
        return int(asset_id) if asset_id else None

    def select_costume(self, session_id: int, story_image_id: int):
        session = self.get_session(session_id)
        row = self._image_repo.get(story_image_id)
        if not session or not row or row.visual_type not in {"costume_initial", "costume_reference"}:
            return None
        owner_session = self.get_session(row.session_id)
        if (
            not owner_session
            or owner_session.story_id != session.story_id
            or owner_session.owner_user_id != session.owner_user_id
        ):
            return None
        state_row = self._state_service.get_state(session_id)
        state_json = self._state_service.load_json(state_row.state_json if state_row else None, fallback=self._state_service.default_state())
        visual = state_json.setdefault("visual_state", {})
        visual["selected_costume_image_id"] = row.id
        visual["selected_costume_asset_id"] = row.asset_id
        self._state_service.upsert_state(session_id, state_json)
        data = self.serialize_image(row)
        data["image_type"] = row.visual_type
        data["is_shared"] = row.session_id != session_id
        data["is_selected"] = True
        return data

    def generate_costume(self, session_id: int, payload: dict | None = None):
        session = self.get_session(session_id)
        if not session:
            return None
        payload = dict(payload or {})
        instruction = str(payload.get("prompt_text") or "").strip()
        if not instruction:
            raise ValueError("prompt_text is required")
        context = self._build_generation_context(session)
        selected = self._selected_costume_image(session.id)
        reference_asset_ids = []
        reference_paths = []
        if selected:
            asset = self._asset_service.get_asset(selected.asset_id)
            if asset and getattr(asset, "file_path", None):
                reference_asset_ids.append(asset.id)
                reference_paths.append(asset.file_path)
        if not reference_paths:
            reference_paths, reference_asset_ids = self._collect_reference_assets(context)
        if not reference_paths:
            raise ValueError("costume reference image is required")
        character = context.get("character") or {}
        costume_context = self._build_costume_context_text(context)
        rewrite = text_support.rewrite_costume_instruction(
            self._text_ai_client,
            context,
            character,
            instruction,
            costume_context,
        )
        rewritten_instruction = rewrite.get("rewritten_instruction") or instruction
        safety_note = rewrite.get("safety_note") or ""
        negative_note = rewrite.get("negative_note") or ""
        prompt = "\n".join(
            [
                "同一キャラクターの衣装参照画像を生成してください。",
                "参照画像と同じ人物として、顔、髪型、体型、雰囲気、キャラクター性を保つ。",
                "参照画像の画風、写実度、ライティング、色調、質感を最優先で維持する。",
                "変更するのは主に衣装と小物のみ。別人化、別画風化、文字、ロゴ、透かしは禁止。",
                f"画像生成向けに整理した衣装指示:\n{rewritten_instruction}",
                f"安全な表現方針:\n{safety_note}",
                f"避ける表現:\n{negative_note}",
                f"キャラクター: {character.get('name') or ''}",
                f"性格・雰囲気: {character.get('personality') or ''}",
                f"会話と現在場面の文脈:\n{costume_context}",
                "TRPGセッション用の衣装差分として、全身または膝上、衣装が分かる構図、シンプル背景。",
                "かわいさ、冒険感、適度な色気はファッション表現で出し、露骨な性的表現にはしない。",
            ]
        )
        prompt = prompt_support.forbid_text_in_image(prompt)
        result = self._image_ai_client.generate_image(
            prompt,
            size=payload.get("size") or "1024x1536",
            quality=payload.get("quality") or "medium",
            model=payload.get("model") or payload.get("image_ai_model"),
            provider=payload.get("provider") or payload.get("image_ai_provider"),
            input_image_paths=reference_paths,
            input_fidelity="high",
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("costume image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_image(session, image_base64)
        asset = self._asset_service.create_asset(
            session.project_id,
            {
                "asset_type": "story_costume_reference",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "story_costume_room",
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "instruction": instruction,
                        "rewritten_instruction": rewritten_instruction,
                        "safety_note": safety_note,
                        "negative_note": negative_note,
                        "reference_asset_ids": reference_asset_ids,
                        "revised_prompt": result.get("revised_prompt"),
                    }
                ),
            },
        )
        row = self._image_repo.create(
            {
                "session_id": session.id,
                "asset_id": asset.id,
                "visual_type": "costume_reference",
                "subject": instruction[:255],
                "prompt_text": result.get("revised_prompt") or prompt,
                "reference_asset_ids_json": json_util.dumps(reference_asset_ids),
                "metadata_json": json_util.dumps(
                    {
                        "source": "story_costume_room",
                        "story_id": session.story_id,
                        "instruction": instruction,
                        "rewritten_instruction": rewritten_instruction,
                        "safety_note": safety_note,
                        "negative_note": negative_note,
                    }
                ),
            }
        )
        return self.select_costume(session_id, row.id)

    def register_uploaded_costume(self, session_id: int, asset_id: int, payload: dict | None = None):
        session = self.get_session(session_id)
        asset = self._asset_service.get_asset(asset_id)
        if not session or not asset:
            return None
        payload = dict(payload or {})
        row = self._image_repo.create(
            {
                "session_id": session.id,
                "asset_id": asset.id,
                "visual_type": "costume_reference",
                "subject": payload.get("prompt_text") or "アップロード衣装",
                "prompt_text": payload.get("prompt_text") or "衣装ルームでアップロードした衣装画像",
                "reference_asset_ids_json": json_util.dumps([asset.id]),
                "metadata_json": json_util.dumps(
                    {
                        "source": "story_costume_upload",
                        "story_id": session.story_id,
                        "note": payload.get("note") or "",
                    }
                ),
            }
        )
        return self.select_costume(session.id, row.id)

    def delete_costume(self, session_id: int, story_image_id: int):
        session = self.get_session(session_id)
        row = self._image_repo.get(story_image_id)
        if not session or not row or row.session_id != session.id or row.visual_type != "costume_reference":
            return None
        result = self._image_repo.delete_costume(session.id, row.id)
        if not result:
            return None
        state_row = self._state_service.get_state(session.id)
        state_json = self._state_service.load_json(state_row.state_json if state_row else None, fallback=self._state_service.default_state())
        visual = state_json.setdefault("visual_state", {})
        if int(visual.get("selected_costume_image_id") or 0) == int(story_image_id):
            visual.pop("selected_costume_image_id", None)
            visual.pop("selected_costume_asset_id", None)
            self._state_service.upsert_state(session.id, state_json)
            self.ensure_initial_costume(session.id)
        selected = self._selected_costume_image(session.id)
        return {
            "session_id": session.id,
            "deleted_id": result.get("deleted_id"),
            "selected_costume": self.serialize_image(selected) if selected else None,
            "costumes": self.list_costumes(session.id),
        }

    def _build_costume_context_text(self, context: dict):
        state = context.get("state") or {}
        game = state.get("game_state") or {}
        relationship = state.get("relationship_state") or {}
        messages = []
        for message in (context.get("recent_messages") or [])[-8:]:
            speaker = message.get("speaker_name") or message.get("sender_type") or ""
            text = str(message.get("message_text") or "").strip()
            if text:
                messages.append(f"{speaker}: {text[:220]}")
        visible_items = self._visible_items_for_prompt(state)
        return "\n".join(
            part
            for part in [
                f"現在地: {game.get('location') or ''}",
                f"現在目的: {context.get('current_goal') or ''}",
                f"危険度: {game.get('danger') or 0}",
                f"親密度: {relationship.get('affection') or 0}",
                f"緊張度: {relationship.get('tension') or 0}",
                "見える所持品・装備: " + " / ".join(visible_items) if visible_items else "",
                "直近の会話:",
                "\n".join(messages),
            ]
            if str(part or "").strip()
        )

    def _main_character_name(self, session):
        snapshot = self._state_service.load_json(session.story_snapshot_json)
        story = self._story_service.get_story(session.story_id)
        if story:
            character = self._character_service.get_character(story.character_id)
            if character:
                return character.name
        return snapshot.get("character_name") or "Character"

    def _build_generation_context(self, session):
        story = self._story_service.get_story(session.story_id)
        character = self._character_service.get_character(story.character_id) if story else None
        state = self._state_service.serialize_state(self._state_service.get_state(session.id)) or {}
        messages = [self.serialize_message(message) for message in self._message_repo.list_by_session(session.id)]
        snapshot = self._state_service.load_json(session.story_snapshot_json)
        state_json = state.get("state_json") or {}
        config_json = snapshot.get("config_json") if isinstance(snapshot.get("config_json"), dict) else {}
        goal_state = state_json.get("goal_state") if isinstance(state_json.get("goal_state"), dict) else {}
        current_goal = (
            goal_state.get("current_goal")
            or goal_state.get("main_goal")
            or config_json.get("current_goal")
            or config_json.get("main_goal")
            or config_json.get("goal")
        )
        return {
            "session": self.serialize_session(session, include_state=False, include_messages=False),
            "story": self._story_service.serialize_story(story) if story else None,
            "story_snapshot": snapshot,
            "character": self._serialize_character_for_prompt(character),
            "world_map": self._world_map_context(session.project_id),
            "state": state_json,
            "current_goal": str(current_goal or "").strip(),
            "clear_conditions": goal_state.get("clear_conditions") or config_json.get("clear_conditions") or [],
            "recent_messages": messages[-10:],
        }

    def _world_map_context(self, project_id: int):
        try:
            return {
                "locations": self._world_map_service.list_locations(project_id)[:20],
                "prompt_context": self._world_map_service.location_prompt_context(project_id, limit=20),
            }
        except Exception:
            return {"locations": [], "prompt_context": ""}

    def _serialize_character_for_prompt(self, character):
        if not character:
            return {}
        memory_profile = self._state_service.load_json(getattr(character, "memory_profile_json", None))
        if not isinstance(memory_profile, dict):
            memory_profile = {}
        favorite_items = self._state_service.load_json(getattr(character, "favorite_items_json", None))
        if not isinstance(favorite_items, list):
            favorite_items = []
        feed_profile = self._feed_repository.get_profile(character.id)
        return {
            "id": character.id,
            "name": character.name,
            "nickname": getattr(character, "nickname", None),
            "gender": getattr(character, "gender", None),
            "age_impression": getattr(character, "age_impression", None),
            "appearance_summary": getattr(character, "appearance_summary", None),
            "art_style": getattr(character, "art_style", None),
            "personality": getattr(character, "personality", None),
            "speech_style": getattr(character, "speech_style", None),
            "speech_sample": getattr(character, "speech_sample", None),
            "first_person": getattr(character, "first_person", None),
            "second_person": getattr(character, "second_person", None),
            "ng_rules": getattr(character, "ng_rules", None),
            "memory_notes": getattr(character, "memory_notes", None),
            "favorite_items": favorite_items,
            "memory_profile": memory_profile,
            "feed_profile_text": getattr(feed_profile, "profile_text", None) if feed_profile else None,
        }

    def _serialize_asset(self, asset):
        if not asset:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "file_path": asset.file_path,
            "mime_type": asset.mime_type,
            "file_size": asset.file_size,
            "media_url": self._build_media_url(asset.file_path),
        }

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
        relative_path = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative_path}"

    def _generate_gm_result(self, context: dict, user_text: str):
        prompt = self._build_gm_prompt(context, user_text)
        try:
            result = self._text_ai_client.generate_text(prompt, temperature=0.75, response_format={"type": "json_object"})
            parsed = self._text_ai_client._try_parse_json(result.get("text"))
            if isinstance(parsed, dict):
                return self._normalize_gm_result(parsed, context, user_text)
        except Exception:
            pass
        return self._fallback_gm_result(context["session"]["id"], user_text, context)

    def _create_scene_messages(self, session, gm_result: dict, context: dict, user_text: str):
        messages = []
        scene_messages = gm_result.get("scene_messages") if isinstance(gm_result.get("scene_messages"), list) else []
        if not scene_messages:
            scene_messages = [
                {"sender_type": "gm", "speaker_name": "GM", "message_text": gm_result.get("narration") or ""},
                {
                    "sender_type": "character",
                    "speaker_name": self._main_character_name(session),
                    "message_text": self._generate_character_line(context, user_text),
                },
            ]
        for index, item in enumerate(scene_messages):
            if not isinstance(item, dict):
                continue
            text = str(item.get("message_text") or item.get("text") or "").strip()
            if not text:
                continue
            sender_type = str(item.get("sender_type") or item.get("type") or "").strip()
            if sender_type in {"player", "user", "pc"}:
                sender_type = "player"
                speaker_name = session.player_name
                message_type = "dialogue"
                text = self._normalize_player_text(text, context)
            elif sender_type in {"character", "npc"}:
                sender_type = "character"
                speaker_name = self._main_character_name(session)
                message_type = "dialogue"
            else:
                sender_type = "gm"
                speaker_name = item.get("speaker_name") or "GM"
                message_type = "narration"
            messages.append(
                self.create_message(
                    session.id,
                    {
                        "sender_type": sender_type,
                        "speaker_name": speaker_name,
                        "message_text": text,
                        "message_type": str(item.get("message_type") or message_type),
                        "metadata_json": {"gm_result": gm_result} if index == 0 else None,
                    },
                )
            )
        return messages

    def _build_gm_prompt(self, context: dict, user_text: str):
        character_name = self._main_character_display_name(context)
        player_name = self._player_display_name(context)
        turn_plan = self._story_turn_plan(context)
        return "\n".join(
            [
                "あなたはTRPGセッションのゲームマスター(directionAI)です。",
                "キャラクター本人のセリフは作らず、状況裁定、状態更新案、次の3択をJSONで返します。",
                "このセッションの現在目的を常に意識し、裁定・状態更新・選択肢の少なくとも1つを目的へ近づけてください。",
                "失敗や危険な行動も単なる罰にせず、秘密、親密さ、謎、危険のどれかが深まる展開にしてください。",
                "キャラクターが自分の意思で動く気まぐれ行動を、必要なら gm_event.character_initiative に入れてください。",
                f"プレイヤー名は「{player_name}」、相手キャラクター名は「{character_name}」です。",
                f"next_choicesはプレイヤーの行動文です。相手キャラクターを指すときは「あなた」ではなく「{character_name}」と書いてください。",
                f"このセッションは全{turn_plan['max_turns']}ターンで必ず完結します。現在は{turn_plan['turn_number']}/{turn_plan['max_turns']}ターン目です。",
                f"このターンの役割は「{turn_plan['phase_label']}」です。scene_messagesとstate_patchは必ずこの役割に沿わせてください。",
                f"残り{turn_plan['remaining_turns']}ターンです。残りターン数に合わせて、導入、探索、危機、最終選択、エンディングの密度を調整してください。",
                f"{turn_plan['max_turns'] - 2}ターン目以降は新しい大謎を追加せず、既存の謎・目的・関係性を回収してください。",
                f"{turn_plan['max_turns'] - 1}ターン目は最終選択です。next_choicesは結末を分ける3択にしてください。",
                f"{turn_plan['max_turns']}ターン目はエンディングです。物語を必ず完結させ、next_choicesは空配列にしてください。",
                "毎ターン、必ず物語を前進させてください。雰囲気描写だけで終わらせず、progress_delta は原則 1 以上にしてください。",
                "毎ターン必ずイベントを1つ起こしてください。イベントは、場所移動、手がかり発見、障害発生、敵や人物の登場、アイテム入手、目的更新、秘密暴露、親密な急接近、危険の接近のいずれかです。",
                "そのターンで起こしたイベントは gm_event.turn_event に短く書き、state_patch の location/progress_delta/flags_add/open_threads_add/inventory.add/relationship_state/visual_state の少なくとも1つにも必ず反映してください。",
                "プレイヤーが雑談や確認だけをしても、相手キャラクターの気づき、物音、違和感、危険の接近などで場面を動かしてください。",
                "1回の入力に対して scene_messages を4〜7件作ってください。各メッセージは長文でよく、画面側でページ送りします。",
                "scene_messages は GM描写、プレイヤー自動発話、キャラクター発話を交互に含めてください。プレイヤーも自分で考えて話し、行動してください。",
                "scene_messages の最後では必ず次のステージ、次の部屋、次の局面、次の目的のいずれかへ移動する内容にしてください。",
                "ユーザーが操作するのは最後の next_choices だけです。途中でユーザー判断を待つ文章にしないでください。",
                "Required keys: narration, scene_messages, state_patch, next_choices, gm_event.",
                "gm_event schema: {turn_event: string, event_type: 'move|clue|obstacle|encounter|item|goal|secret|romance|danger', character_initiative: string}.",
                "scene_messages item schema: {sender_type: 'gm|player|character', speaker_name: string, message_text: string}.",
                "next_choicesは3件。rolesは explore, romance, risk を基本にします。",
                "state_patchの数値deltaは -20 から 20 の範囲にしてください。",
                "state_patch schema:",
                json_util.dumps(
                    {
                        "game_state": {
                            "location": "新しい現在地があれば文字列",
                            "progress_delta": 1,
                            "danger_delta": 0,
                            "flags_add": ["日本語の短い進行メモ。例: 古井戸の鍵を発見した"],
                            "open_threads_add": ["日本語の短い未解決メモ。例: 鍵に月の紋章が刻まれている"],
                        },
                        "relationship_state": {
                            "affection_delta": 0,
                            "trust_delta": 0,
                            "tension_delta": 0,
                            "romance_stage_delta": 0,
                        },
                        "inventory": {
                            "add": [
                                {
                                    "id": "snake_case_unique_id",
                                    "name": "表示名",
                                    "type": "item|weapon|key|clue",
                                    "owner": "player|character",
                                    "equipped": False,
                                    "visible": True,
                                    "visual_description": "画像生成に使う見た目",
                                    "visibility_priority": 50,
                                }
                            ]
                        },
                        "visual_state": {
                            "active_visual_type": "location|item|encounter|romance|danger",
                            "active_subject": "次の画像の中心",
                        },
                        "goal_state": {
                            "current_goal": "次に目指す具体的な目的",
                            "completed_goals": ["達成済みの目的"],
                            "session_status": "active|clear_ready|cleared",
                        },
                    },
                ),
                "ユーザーが拾う、渡す、装備する、鍵を見つける、宝箱を開ける等をしたら inventory.add を必ず使ってください。",
                "場所移動、扉を開ける、階層移動、イベント進行が起きたら location/progress_delta/flags_add/open_threads_add を更新してください。",
                "flags_add と open_threads_add はUIに表示されるため、snake_caseや英語IDではなく、ユーザーが読める自然な日本語の短文にしてください。",
                "Current goal:",
                str(context.get("current_goal") or "未設定"),
                "Turn plan:",
                json_util.dumps(turn_plan),
                "Clear conditions:",
                json_util.dumps(context.get("clear_conditions") or []),
                "World map locations:",
                json_util.dumps((context.get("world_map") or {}).get("locations") or []),
                "Story JSON:",
                json_util.dumps(context.get("story") or {}),
                "Session state:",
                json_util.dumps(context.get("state") or {}),
                "Character:",
                json_util.dumps(context.get("character") or {}),
                "Recent messages:",
                json_util.dumps(context.get("recent_messages") or []),
                f"User input: {user_text}",
            ]
        )

    def _normalize_gm_result(self, parsed: dict, context: dict, user_text: str):
        turn_plan = self._story_turn_plan(context)
        narration = str(parsed.get("narration") or "").strip()
        if not narration:
            narration = f"{user_text}。その行動で場面が動いた。"
        state_patch = parsed.get("state_patch") if isinstance(parsed.get("state_patch"), dict) else {}
        state_patch = self._normalize_state_patch(state_patch, context)
        state_patch = self._enforce_story_progress(state_patch, context, user_text, turn_plan)
        scene_messages = self._normalize_scene_messages(parsed.get("scene_messages"), context, narration, user_text, turn_plan)
        choices = parsed.get("next_choices") if isinstance(parsed.get("next_choices"), list) else []
        normalized_choices = []
        roles = ["explore", "romance", "risk"]
        if not turn_plan["is_ending"]:
            for index, item in enumerate(choices[:3]):
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label") or "").strip()
                if not label:
                    continue
                label = self._normalize_player_text(label, context)
                normalized_choices.append(
                    {
                        "id": str(item.get("id") or f"choice_{index + 1}"),
                        "label": label[:40],
                        "role": str(item.get("role") or roles[min(index, len(roles) - 1)]),
                        "intent": str(item.get("intent") or "").strip(),
                    }
                )
            if len(normalized_choices) < 3:
                normalized_choices = self._fallback_choices(context, turn_plan)[:3]
        state_patch.setdefault("choice_state", {})["last_choices"] = normalized_choices
        state_patch.setdefault("event_state", {})["turn_count_delta"] = 1
        gm_event = parsed.get("gm_event") if isinstance(parsed.get("gm_event"), dict) else {}
        if not str(gm_event.get("turn_event") or "").strip():
            event_state = state_patch.get("event_state") if isinstance(state_patch.get("event_state"), dict) else {}
            gm_event["turn_event"] = str(event_state.get("turn_event") or self._progress_subject(context, user_text))
        gm_event.setdefault("event_type", "event")
        return {
            "narration": narration,
            "scene_messages": scene_messages,
            "state_patch": state_patch,
            "next_choices": normalized_choices,
            "gm_event": gm_event,
        }

    def _normalize_scene_messages(self, value, context: dict, narration: str, user_text: str, turn_plan: dict | None = None):
        if not isinstance(value, list):
            return self._fallback_scene_messages(context, user_text, narration, turn_plan)
        normalized = []
        character_name = self._main_character_display_name(context)
        player_name = self._player_display_name(context)
        for item in value[:7]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("message_text") or item.get("text") or "").strip()
            if not text:
                continue
            sender_type = str(item.get("sender_type") or item.get("type") or "").strip().lower()
            if sender_type in {"user", "player", "pc"}:
                sender_type = "player"
                speaker_name = player_name
                text = self._normalize_player_text(text, context)
            elif sender_type in {"character", "npc"}:
                sender_type = "character"
                speaker_name = character_name
            else:
                sender_type = "gm"
                speaker_name = "GM"
            normalized.append({"sender_type": sender_type, "speaker_name": speaker_name, "message_text": text})
        if len(normalized) < 4:
            return self._fallback_scene_messages(context, user_text, narration, turn_plan)
        return normalized

    def _fallback_scene_messages(self, context: dict, user_text: str, narration: str, turn_plan: dict | None = None):
        turn_plan = turn_plan or self._story_turn_plan(context)
        character_name = self._main_character_display_name(context)
        player_name = self._player_display_name(context)
        goal = str(context.get("current_goal") or "次の目的").strip()
        action = str(user_text or "選んだ行動").strip()
        if turn_plan.get("is_ending"):
            return [
                {
                    "sender_type": "gm",
                    "speaker_name": "GM",
                    "message_text": narration or f"{action}をきっかけに、最後の場面が静かに動き出す。",
                },
                {
                    "sender_type": "player",
                    "speaker_name": player_name,
                    "message_text": self._normalize_player_text(f"{character_name}、ここまで来たなら最後まで見届けよう。何が残っても、俺はこの結末を選ぶ。", context),
                },
                {
                    "sender_type": "character",
                    "speaker_name": character_name,
                    "message_text": f"……うん。{player_name}とここまで来たこと、忘れない。怖くても、これで終わらせよう。",
                },
                {
                    "sender_type": "gm",
                    "speaker_name": "GM",
                    "message_text": f"二人の選択によって、{goal}を巡る物語はここで決着した。残された痛みも、得たものも、次へ進むための証として胸に残る。セッションは完結した。",
                },
            ]
        return [
            {
                "sender_type": "gm",
                "speaker_name": "GM",
                "message_text": narration or f"{action}をきっかけに、場面が大きく動き出す。",
            },
            {
                "sender_type": "player",
                "speaker_name": player_name,
                "message_text": self._normalize_player_text(f"{character_name}、ここで止まっていたらまた同じことの繰り返しだ。気になる場所まで一気に進もう。", context),
            },
            {
                "sender_type": "character",
                "speaker_name": character_name,
                "message_text": f"……うん。{player_name}がそう言うなら、私も覚悟を決める。次に見えるものから目を逸らさない。",
            },
            {
                "sender_type": "gm",
                "speaker_name": "GM",
                "message_text": f"二人は足を止めず、{goal}へ近づくための次のステージへ踏み込んだ。空気が変わり、新しい選択を迫る気配がはっきりと立ち上がる。",
            },
        ]

    def _enforce_story_progress(self, patch: dict, context: dict, user_text: str, turn_plan: dict | None = None):
        turn_plan = turn_plan or self._story_turn_plan(context)
        normalized = dict(patch or {})
        game_state = normalized.setdefault("game_state", {})
        visual_state = normalized.setdefault("visual_state", {})
        event_state = normalized.setdefault("event_state", {})
        goal_state = normalized.setdefault("goal_state", {})
        inventory_patch = normalized.get("inventory") if isinstance(normalized.get("inventory"), dict) else {}
        goal_patch = goal_state

        goal_state["max_turns"] = turn_plan["max_turns"]
        goal_state["current_turn"] = turn_plan["turn_number"]
        goal_state["current_phase"] = turn_plan["phase"]
        goal_state["current_phase_label"] = turn_plan["phase_label"]
        if turn_plan["is_final_choice"]:
            goal_state["session_status"] = "final_choice"
        elif turn_plan["is_ending"]:
            goal_state["session_status"] = str(goal_state.get("session_status") or "cleared")
            if goal_state["session_status"] not in {"cleared", "failed", "bittersweet_end"}:
                goal_state["session_status"] = "cleared"

        progressed = any(
            [
                self._safe_int(game_state.get("progress_delta")) > 0,
                "progress" in game_state and self._safe_int(game_state.get("progress")) > self._safe_int(((context.get("state") or {}).get("game_state") or {}).get("progress")),
                bool(str(game_state.get("location") or "").strip()),
                bool(game_state.get("flags_add")),
                bool(game_state.get("open_threads_add")),
                bool(inventory_patch.get("add")),
                bool(str(visual_state.get("active_subject") or "").strip()),
                bool(str(goal_patch.get("current_goal") or "").strip()),
                bool(goal_patch.get("completed_goals")),
            ]
        )
        if not progressed:
            game_state["progress_delta"] = 1
            visual_state.setdefault("active_visual_type", "event")
            visual_state.setdefault("active_subject", self._progress_subject(context, user_text))

        current_event = ((context.get("state") or {}).get("event_state") or {})
        next_turn = self._safe_int(current_event.get("turn_count")) + 1
        if next_turn > 0:
            minimum_progress = 2 if next_turn % 3 == 0 and not turn_plan["is_closing"] else 1
            game_state["progress_delta"] = max(minimum_progress, self._safe_int(game_state.get("progress_delta")))
            open_threads = game_state.setdefault("open_threads_add", [])
            if isinstance(open_threads, list):
                thread = self._progress_thread(context, user_text)
                if thread not in open_threads:
                    open_threads.append(thread)
            visual_state.setdefault("active_visual_type", "event")
            visual_state.setdefault("active_subject", self._progress_subject(context, user_text))
            event_state["turn_event"] = str(event_state.get("turn_event") or self._progress_subject(context, user_text))
            event_state["last_event_turn"] = next_turn

        current_goal = str(context.get("current_goal") or "").strip()
        if current_goal:
            normalized.setdefault("goal_state", {}).setdefault("current_goal", current_goal)
        if turn_plan["is_ending"]:
            completed = goal_state.setdefault("completed_goals", [])
            if isinstance(completed, list) and current_goal and current_goal not in completed:
                completed.append(current_goal)
            game_state["progress_delta"] = max(1, self._safe_int(game_state.get("progress_delta")))
        return normalized

    def _safe_int(self, value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _story_turn_plan(self, context: dict):
        state = context.get("state") or {}
        event_state = state.get("event_state") if isinstance(state.get("event_state"), dict) else {}
        goal_state = state.get("goal_state") if isinstance(state.get("goal_state"), dict) else {}
        config = ((context.get("story_snapshot") or {}).get("config_json") or {}) if isinstance((context.get("story_snapshot") or {}).get("config_json"), dict) else {}
        max_turns = self._safe_int(goal_state.get("max_turns") or config.get("max_turns") or 10) or 10
        max_turns = max(5, min(20, max_turns))
        turn_number = min(max_turns, self._safe_int(event_state.get("turn_count")) + 1)
        phases = [
            ("opening", "導入・目的提示"),
            ("first_obstacle", "最初の障害"),
            ("clue_or_item", "手がかりまたはアイテム獲得"),
            ("relationship_shift", "関係性の変化"),
            ("midpoint_crisis", "中盤の事件・危険上昇"),
            ("secret_or_betrayal", "秘密暴露または裏切り"),
            ("final_area", "最終地点への到達"),
            ("cost_before_final", "ラスト前の代償提示"),
            ("final_choice", "最終選択"),
            ("ending", "エンディング・完結"),
        ]
        if max_turns == 10:
            phase_index = turn_number - 1
        else:
            phase_index = round((turn_number - 1) * (len(phases) - 1) / max(1, max_turns - 1))
        phase_index = max(0, min(len(phases) - 1, phase_index))
        phase, phase_label = phases[phase_index]
        if turn_number >= max_turns:
            phase, phase_label = "ending", "エンディング・完結"
        elif turn_number == max_turns - 1:
            phase, phase_label = "final_choice", "最終選択"
        return {
            "turn_number": turn_number,
            "max_turns": max_turns,
            "remaining_turns": max(0, max_turns - turn_number),
            "phase": phase,
            "phase_label": phase_label,
            "is_closing": turn_number >= max_turns - 2,
            "is_final_choice": turn_number == max_turns - 1,
            "is_ending": turn_number >= max_turns,
        }

    def _progress_subject(self, context: dict, user_text: str):
        goal = str(context.get("current_goal") or "").strip()
        action = str(user_text or "").strip()
        if goal:
            return f"{goal}へ向けて動く場面"
        if action:
            return f"{action[:24]}の結果で動く場面"
        return "物語が進展する場面"

    def _progress_thread(self, context: dict, user_text: str):
        goal = str(context.get("current_goal") or "").strip()
        action = str(user_text or "").strip()
        if goal:
            return f"目的「{goal}」に関わる新しい変化が起きた"
        if action:
            return f"行動「{action[:24]}」をきっかけに新しい変化が起きた"
        return "新しい変化が起きた"

    def _normalize_state_patch(self, patch: dict, context: dict | None = None):
        normalized = dict(patch or {})
        game_state = normalized.setdefault("game_state", {})
        if isinstance(game_state, dict):
            inventory_add = game_state.pop("inventory_add", None)
            if isinstance(inventory_add, list):
                if not isinstance(normalized.get("inventory"), dict):
                    normalized["inventory"] = {"add": normalized.get("inventory") if isinstance(normalized.get("inventory"), list) else []}
                normalized["inventory"].setdefault("add", []).extend(inventory_add)
            flags = game_state.get("flags")
            if isinstance(flags, list) and "flags_add" not in game_state:
                game_state["flags_add"] = flags
            open_threads = game_state.get("open_threads")
            if isinstance(open_threads, list) and "open_threads_add" not in game_state:
                game_state["open_threads_add"] = open_threads
            self._guard_location_patch(game_state, context or {})
        inventory = normalized.get("inventory")
        if isinstance(inventory, list):
            normalized["inventory"] = {"add": inventory}
        elif isinstance(inventory, dict):
            add_items = inventory.get("add") or inventory.get("items_add") or inventory.get("inventory_add")
            if isinstance(add_items, list):
                inventory["add"] = add_items
        self._guard_inventory_owners(normalized.get("inventory"), context or {})
        return normalized

    def _guard_location_patch(self, game_state: dict, context: dict):
        location = str(game_state.get("location") or "").strip()
        if not location:
            return
        known_locations = self._known_locations_for_context(context)
        if not known_locations:
            return
        normalized_location = self._normalize_compare_value(location)
        allowed = any(
            normalized_location == known
            or normalized_location in known
            or known in normalized_location
            for known in known_locations
        )
        if allowed:
            return
        game_state.pop("location", None)
        ignored = f"未定義の場所「{location}」への移動を無視した"
        game_state.setdefault("open_threads_add", [])
        if isinstance(game_state["open_threads_add"], list):
            game_state["open_threads_add"].append(ignored)

    def _known_locations_for_context(self, context: dict):
        story = context.get("story") or {}
        snapshot = context.get("story_snapshot") or {}
        state = context.get("state") or {}
        config = story.get("config_json") if isinstance(story.get("config_json"), dict) else {}
        snapshot_config = snapshot.get("config_json") if isinstance(snapshot.get("config_json"), dict) else {}
        initial = story.get("initial_state_json") if isinstance(story.get("initial_state_json"), dict) else {}
        snapshot_initial = snapshot.get("initial_state_json") if isinstance(snapshot.get("initial_state_json"), dict) else {}
        values = []
        for source in (config, snapshot_config):
            values.extend(self._extract_config_locations(source))
        for source in (initial, snapshot_initial, state):
            game = source.get("game_state") if isinstance(source, dict) else {}
            if isinstance(game, dict) and game.get("location"):
                values.append(game.get("location"))
        return {
            self._normalize_compare_value(item)
            for item in values
            if self._normalize_compare_value(item)
        }

    def _extract_config_locations(self, config: dict):
        if not isinstance(config, dict):
            return []
        values = []
        for key in ("locations", "places", "areas", "stages", "map"):
            values.extend(self._extract_location_values(config.get(key)))
        return values

    def _extract_location_values(self, value):
        values = []
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            for item in value:
                values.extend(self._extract_location_values(item))
        elif isinstance(value, dict):
            for key in ("id", "name", "title", "location", "location_name"):
                if value.get(key):
                    values.append(value.get(key))
            for key in ("children", "areas", "rooms", "locations", "stages"):
                values.extend(self._extract_location_values(value.get(key)))
        return values

    def _guard_inventory_owners(self, inventory_patch, context: dict):
        if not isinstance(inventory_patch, dict) or not isinstance(inventory_patch.get("add"), list):
            return
        allowed_owners = self._known_owner_tokens(context)
        for item in inventory_patch["add"]:
            if not isinstance(item, dict):
                continue
            owner = self._normalize_compare_value(item.get("owner") or "player")
            if owner not in allowed_owners:
                item["owner"] = "player"

    def _known_owner_tokens(self, context: dict):
        character = context.get("character") or {}
        snapshot = context.get("story_snapshot") or {}
        owners = {"player", "user", "character"}
        for value in (
            character.get("id"),
            character.get("name"),
            character.get("nickname"),
            snapshot.get("character_id"),
            snapshot.get("character_name"),
        ):
            normalized = self._normalize_compare_value(value)
            if normalized:
                owners.add(normalized)
        return owners

    def _normalize_compare_value(self, value):
        return str(value or "").strip().casefold()

    def _generate_character_line(self, context: dict, user_text: str):
        prompt = self._build_character_prompt(context, user_text)
        try:
            result = self._text_ai_client.generate_text(prompt, temperature=0.8, response_format={"type": "json_object"})
            parsed = self._text_ai_client._try_parse_json(result.get("text"))
            if isinstance(parsed, dict):
                text = str(parsed.get("message_text") or "").strip()
                if text:
                    return text
        except Exception:
            pass
        player_name = self._player_display_name(context)
        return f"……わかりました。少し怖いですけど、{player_name}となら進めます。"

    def _build_character_prompt(self, context: dict, user_text: str):
        player_name = self._player_display_name(context)
        return "\n".join(
            [
                "あなたはTRPGセッション内のキャラクターAIです。",
                "GM裁定を事実として扱い、裁定を上書きしないでください。",
                "キャラクター本人の口調、感情、関係性を反映して短いセリフを返してください。",
                "speech_style, speech_sample, first_person, second_person, personality, memory_notes, memory_profile, favorite_items, feed_profile_text を強く反映してください。",
                f"相手プレイヤーを呼ぶときは、second_personに明確な呼称がない限り「あなた」ではなく「{player_name}」と呼んでください。",
                "feed_profile_text は公開投稿から要約されたキャラクター傾向です。矛盾しない範囲で、話題選び・温度感・反応の癖に使ってください。",
                "ng_rules がある場合は必ず守ってください。",
                "現在の状況、所持品、未解決の謎、親密度、緊張度を自然に使ってください。",
                "同じ甘い反応だけを繰り返さず、必要なら不安、秘密、探索への促しも混ぜてください。",
                "Return JSON only. Required key: message_text.",
                "Character:",
                json_util.dumps(context.get("character") or {}),
                "Session:",
                json_util.dumps(context.get("session") or {}),
                "Session state:",
                json_util.dumps(context.get("state") or {}),
                "World map locations:",
                json_util.dumps((context.get("world_map") or {}).get("locations") or []),
                "GM result:",
                json_util.dumps(context.get("gm_result") or {}),
                "Recent messages:",
                json_util.dumps(context.get("recent_messages") or []),
                f"User input: {user_text}",
            ]
        )

    def _build_player_draft_prompt(self, context: dict, payload: dict):
        character_name = self._main_character_display_name(context)
        player_name = self._player_display_name(context)
        return "\n".join(
            [
                "あなたはTRPGセッションのプレイヤー入力の下書きを作るAIです。",
                "ユーザーの代わりに、次に入力すると面白くなる短い行動文またはセリフを書いてください。",
                "テキストボックスに入れる文だけを作るので、GM裁定やキャラの返答は書かないでください。",
                "探索、親密、危険のどれかに偏りすぎず、現在の状態と選択肢に合う自然な日本語にしてください。",
                f"プレイヤー名は「{player_name}」、相手キャラクター名は「{character_name}」です。",
                f"プレイヤーが相手キャラクターを呼ぶときは「あなた」ではなく「{character_name}」と呼んでください。",
                "プレイヤー自身の名前を、相手キャラクターへの呼びかけとして使わないでください。",
                "Return JSON only. Required key: message_text.",
                "Story:",
                json_util.dumps(context.get("story") or {}),
                "Character:",
                json_util.dumps(context.get("character") or {}),
                "Session:",
                json_util.dumps(context.get("session") or {}),
                "Session state:",
                json_util.dumps(context.get("state") or {}),
                "World map locations:",
                json_util.dumps((context.get("world_map") or {}).get("locations") or []),
                "Recent messages:",
                json_util.dumps(context.get("recent_messages") or []),
                "Optional user hint:",
                str(payload.get("hint") or ""),
            ]
        )

    def _fallback_choices(self, context: dict, turn_plan: dict | None = None):
        turn_plan = turn_plan or self._story_turn_plan(context)
        relationship = (context.get("state") or {}).get("relationship_state") or {}
        game_state = (context.get("state") or {}).get("game_state") or {}
        affection = int(relationship.get("affection") or 0)
        danger = int(game_state.get("danger") or 0)
        character_name = self._main_character_display_name(context)
        if turn_plan.get("is_final_choice"):
            return [
                {"id": "choice_final_save", "label": f"{character_name}を守って目的を果たす", "role": "romance"},
                {"id": "choice_final_truth", "label": "真実を優先して決着させる", "role": "explore"},
                {"id": "choice_final_risk", "label": "危険な賭けで全てを取りに行く", "role": "risk"},
            ]
        close_choice = f"{character_name}の手を取って進む" if affection >= 30 else f"{character_name}に確認する"
        risk_choice = "危険を承知で奥へ進む" if danger >= 40 else "奥へ進む"
        return [
            {"id": "choice_explore", "label": "周囲を調べる", "role": "explore"},
            {"id": "choice_romance", "label": close_choice, "role": "romance"},
            {"id": "choice_risk", "label": risk_choice, "role": "risk"},
        ]

    def _normalize_player_text(self, text: str, context: dict):
        value = str(text or "").strip()
        character_name = self._main_character_display_name(context)
        if character_name:
            value = value.replace("あなた", character_name)
        return value

    def _main_character_display_name(self, context: dict):
        character = context.get("character") or {}
        snapshot = context.get("story_snapshot") or {}
        story = context.get("story") or {}
        story_character = story.get("character") if isinstance(story.get("character"), dict) else {}
        for value in (
            character.get("name"),
            story_character.get("name"),
            snapshot.get("character_name"),
            character.get("nickname"),
            story_character.get("nickname"),
        ):
            name = str(value or "").strip()
            if name:
                return name
        return "相手"

    def _player_display_name(self, context: dict):
        session = context.get("session") or {}
        player_name = str(session.get("player_name") or "").strip()
        return player_name or "プレイヤー"

    def _fallback_gm_result(self, session_id: int, user_text: str, context: dict):
        turn_plan = self._story_turn_plan(context)
        choices = [] if turn_plan["is_ending"] else self._fallback_choices(context, turn_plan)
        narration = f"{user_text}。その行動に合わせて、場面の空気が少し動いた。"
        return {
            "narration": narration,
            "scene_messages": self._fallback_scene_messages(context, user_text, narration, turn_plan),
            "state_patch": {
                "game_state": {"progress_delta": 2},
                "relationship_state": {"trust_delta": 1, "tension_delta": 1},
                "event_state": {"turn_count_delta": 1},
                "choice_state": {"last_choices": choices},
                "visual_state": {
                    "active_visual_type": "event",
                    "active_subject": self._progress_subject(context, user_text),
                },
                "goal_state": {
                    "max_turns": turn_plan["max_turns"],
                    "current_turn": turn_plan["turn_number"],
                    "current_phase": turn_plan["phase"],
                    "current_phase_label": turn_plan["phase_label"],
                    "session_status": "cleared" if turn_plan["is_ending"] else ("final_choice" if turn_plan["is_final_choice"] else "active"),
                },
            },
            "next_choices": choices,
            "gm_event": {"source": "fallback", "session_id": session_id},
        }

    def _format_roll_message(self, roll: dict):
        target = f" / 目標値 {roll['target']}" if roll.get("target") is not None else ""
        outcome = ""
        if roll.get("outcome") == "success":
            outcome = " 成功"
        elif roll.get("outcome") == "failure":
            outcome = " 失敗"
        reason = f"{roll.get('reason')}: " if roll.get("reason") else ""
        return f"{reason}{roll['formula']} = {roll['total']}{target}{outcome}"

    def _storage_root(self):
        try:
            return current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        except RuntimeError:
            return os.path.join(os.getcwd(), "storage")

    def _store_generated_image(self, session, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated image payload is invalid") from exc
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        directory = os.path.join(self._storage_root(), "projects", str(session.project_id), "generated", "story_session", str(session.id))
        os.makedirs(directory, exist_ok=True)
        file_name = f"story_session_{timestamp}.png"
        file_path = os.path.join(directory, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)

    def _scene_image_options(self, session, payload: dict):
        settings = {}
        try:
            settings = self._user_setting_service.get_settings(session.owner_user_id)
        except Exception:
            settings = {}
        quality = str(payload.get("quality") or settings.get("default_quality") or "medium").strip()
        size = str(payload.get("size") or settings.get("default_size") or "1536x1024").strip()
        provider = str(payload.get("provider") or payload.get("image_ai_provider") or settings.get("image_ai_provider") or "openai").strip()
        model = str(payload.get("model") or payload.get("image_ai_model") or settings.get("image_ai_model") or "").strip()
        if quality not in UserSettingService.VALID_QUALITIES:
            quality = "medium"
        if size not in UserSettingService.VALID_SIZES:
            size = "1536x1024"
        if provider not in UserSettingService.VALID_IMAGE_PROVIDERS:
            provider = "openai"
        return {"quality": quality, "size": size, "provider": provider, "model": model or None}

    def _build_live_chat_visual_context(self, session, context: dict):
        story = context.get("story") or {}
        story_snapshot = context.get("story_snapshot") or {}
        story_config = story.get("config_json") if isinstance(story.get("config_json"), dict) else {}
        snapshot_config = story_snapshot.get("config_json") if isinstance(story_snapshot.get("config_json"), dict) else {}
        config = {**snapshot_config, **story_config}
        character = dict(context.get("character") or {})
        state = context.get("state") or {}
        game = state.get("game_state") or {}
        relationship = state.get("relationship_state") or {}
        visual = state.get("visual_state") or {}
        project = self._project_service.get_project(session.project_id)
        project_settings = self._state_service.load_json(getattr(project, "settings_json", None), fallback={}) if project else {}
        if not isinstance(project_settings, dict):
            project_settings = {}
        for key in ("art_style_profile", "visual_style", "image_style"):
            value = config.get(key)
            if value and not project_settings.get(key):
                project_settings[key] = value
        if config.get("visual_tone"):
            project_settings.setdefault("visual_style", config.get("visual_tone"))
        if story.get("style_prompt"):
            project_settings.setdefault("art_style_profile", story.get("style_prompt"))
        if not character.get("appearance_summary"):
            character["appearance_summary"] = config.get("main_character_appearance") or ""
        if not character.get("art_style"):
            character["art_style"] = config.get("character_art_style") or config.get("visual_style") or ""
        character.setdefault("id", story.get("character_id") or 0)
        character.setdefault("name", (story.get("character") or {}).get("name") or "メインキャラクター")
        live_state = {
            "active_character_ids": [character.get("id")] if character.get("id") else [],
            "location": game.get("location") or visual.get("active_subject") or "",
            "background": game.get("location") or "",
            "mood": self._scene_mood_for_visual_prompt(game, relationship),
            "focus_summary": self._latest_scene_summary(context),
        }
        return {
            "project": {
                "id": session.project_id,
                "title": getattr(project, "title", None) or story.get("title") or "",
                "settings_json": json_util.dumps(project_settings),
            },
            "room": {
                "conversation_objective": context.get("current_goal") or config.get("main_goal") or "",
            },
            "characters": [character] if character else [],
            "state": {"state_json": live_state},
            "messages": context.get("recent_messages") or [],
        }

    def _polish_scene_image_prompt(self, prompt: str, visual_context: dict, payload: dict):
        original_prompt = str(prompt or "").strip()
        refined = prompt_support.normalize_first_person_visual_prompt(original_prompt)
        refined = prompt_support.apply_visual_style(refined, visual_context)
        refined = prompt_support.forbid_text_in_image(refined)
        safety_mode = str(current_app.config.get("IMAGE_PROMPT_SAFETY_MODE", "both")).strip().lower()
        if safety_mode in {"both", "preflight"}:
            safety_rewrite = text_support.rewrite_image_prompt_for_safety(
                self._text_ai_client,
                visual_context,
                refined,
                purpose=str(payload.get("visual_type") or "story_scene"),
            )
        else:
            safety_rewrite = {
                "rewritten_prompt": refined,
                "changed": False,
                "safety_reason": f"preflight safety rewrite disabled by IMAGE_PROMPT_SAFETY_MODE={safety_mode}",
            }
        refined = safety_rewrite.get("rewritten_prompt") or refined
        refined = prompt_support.apply_visual_style(refined, visual_context)
        refined = prompt_support.forbid_text_in_image(refined)
        return refined, {
            "source": "live_chat_image_prompt_pipeline",
            "original_prompt": original_prompt[:6000],
            "safety_rewrite": safety_rewrite,
        }

    def _apply_costume_reference_guardrails(self, prompt: str, reference_asset_ids: list[int]):
        text = str(prompt or "").strip()
        if not reference_asset_ids:
            return text
        guardrails = [
            "重要: 添付された参照画像を現在選択中の衣装基準として扱う。",
            "参照画像と同じ人物、同じ顔立ち、同じ髪型、同じ画風、同じ衣装デザイン、同じ配色、同じ質感を維持する。",
            "シーンやポーズや背景だけを変え、服装を別衣装に変更しない。鎧、制服、ドレス、現代服などへ勝手に置き換えない。",
            "物語上の装備や小物がある場合も、参照衣装の上に自然に持たせるだけにする。",
            "明示的に着替えや衣装変更を指示されていない限り、現在の衣装を最優先で固定する。",
        ]
        return "\n".join([text, *guardrails])

    def _apply_first_person_game_cg_guardrails(self, prompt: str):
        text = str(prompt or "").strip()
        guardrails = [
            "重要: 画像はプレイヤー本人の一人称視点で描く。カメラはプレイヤーの目線位置に置く。",
            "プレイヤー本人の顔や全身は画面に出さない。必要な場合だけ、画面手前に手、持ち物、武器、足元の一部を入れる。",
            "相手キャラクターはプレイヤーの目の前にいて、こちらを見ている、手を伸ばす、近づく、導く、驚く、照れるなど、ユーザーに向いた反応が分かる構図にする。",
            "ゲームのイベントCGとして映える、奥行き、前景、中景、背景、ドラマチックな光、視線誘導、緊張感または親密さのある構図にする。",
            "ただの立ち絵、証明写真、ポートレート、無人の背景、遠すぎる全身図、説明的な小物だけの画像にしない。",
            "画面内にUI、字幕、吹き出し、文字、ロゴ、透かしを入れない。",
        ]
        return "\n".join([text, *guardrails])

    def _scene_mood_for_visual_prompt(self, game: dict, relationship: dict):
        danger = self._safe_int(game.get("danger"))
        affection = self._safe_int(relationship.get("affection"))
        tension = self._safe_int(relationship.get("tension"))
        if danger >= 70:
            return "危険が迫るドラマチックな緊張感"
        if affection >= 60 and tension >= 40:
            return "恋愛の熱と冒険の緊張が混ざった印象的な空気"
        if affection >= 60:
            return "親密で会いたくなる甘い空気"
        if tension >= 50:
            return "謎と駆け引きの緊張感"
        return "物語が動き出すノベルゲームのイベントCGらしい空気"

    def _safe_int(self, value, default: int = 0):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _latest_scene_summary(self, context: dict):
        messages = context.get("recent_messages") or []
        for message in reversed(messages):
            text = str(message.get("message_text") or "").strip()
            if text:
                return text[:180]
        return context.get("current_goal") or ""

    def _collect_reference_assets(self, context: dict):
        reference_paths = []
        reference_asset_ids = []
        session_id = (context.get("session") or {}).get("id")
        selected_costume = self._selected_costume_image(session_id)
        if selected_costume:
            asset = self._asset_service.get_asset(selected_costume.asset_id)
            if asset and getattr(asset, "file_path", None):
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)
        if reference_paths:
            return reference_paths, reference_asset_ids
        outfit = self._default_outfit_for_context(context)
        if outfit:
            asset = self._asset_service.get_asset(outfit.asset_id)
            if asset and getattr(asset, "file_path", None):
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)
                return reference_paths, reference_asset_ids
        story = context.get("story") or {}
        for asset_id in (
            (story.get("character") or {}).get("base_asset_id"),
            story.get("main_character_reference_asset_id"),
        ):
            if not asset_id or asset_id in reference_asset_ids:
                continue
            asset = self._asset_service.get_asset(asset_id)
            if asset and getattr(asset, "file_path", None):
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)
        return reference_paths[:2], reference_asset_ids[:2]

    def _default_outfit_for_context(self, context: dict):
        character_id = int((context.get("character") or {}).get("id") or 0)
        if not character_id:
            character_id = int(((context.get("story") or {}).get("character") or {}).get("id") or 0)
        if not character_id:
            return None
        story = context.get("story") if isinstance(context.get("story"), dict) else {}
        snapshot = context.get("story_snapshot") if isinstance(context.get("story_snapshot"), dict) else {}
        outfit_id = story.get("default_outfit_id") or snapshot.get("default_outfit_id")
        return self._closet_service.resolve_outfit(character_id, outfit_id)

    def _selected_costume_image(self, session_id: int | None):
        if not session_id:
            return None
        state_row = self._state_service.get_state(int(session_id))
        state_json = self._state_service.load_json(state_row.state_json if state_row else None, fallback={})
        visual_state = state_json.get("visual_state") or {}
        image_id = visual_state.get("selected_costume_image_id")
        if image_id:
            row = self._image_repo.get(int(image_id))
            if row and row.visual_type in {"costume_initial", "costume_reference"}:
                return row
        asset_id = visual_state.get("selected_costume_asset_id")
        if not asset_id:
            return None
        row = next(
            (
                item for item in self._image_repo.list_costumes_for_session_library(int(session_id))
                if int(item.asset_id) == int(asset_id)
            ),
            None,
        )
        if row and row.visual_type in {"costume_initial", "costume_reference"}:
            visual_state["selected_costume_image_id"] = row.id
            visual_state["selected_costume_asset_id"] = row.asset_id
            state_json["visual_state"] = visual_state
            self._state_service.upsert_state(int(session_id), state_json)
            return row
        return None

    def _visible_items_for_prompt(self, state: dict):
        items = ((state.get("game_state") or {}).get("inventory") or [])
        visible = []
        for item in items:
            if not isinstance(item, dict) or not item.get("visible"):
                continue
            owner = item.get("owner") or "player"
            description = item.get("visual_description") or item.get("name")
            visible.append(f"{owner}: {description}")
        return visible[:6]

    def _build_scene_image_prompt(self, context: dict):
        state = context.get("state") or {}
        game = state.get("game_state") or {}
        relationship = state.get("relationship_state") or {}
        visual = state.get("visual_state") or {}
        character = context.get("character") or {}
        story = context.get("story") or {}
        visible_items = self._visible_items_for_prompt(state)
        prompt_parts = [
            "現在のTRPGセッション場面を1枚のビジュアルノベル風シーン画像として生成する。",
            f"ストーリー: {story.get('title') or ''}",
            f"場所: {game.get('location') or visual.get('active_subject') or '未知の場所'}",
            f"メインキャラクター: {character.get('name') or ''}",
            f"危険度: {game.get('danger', 0)} / 親密度: {relationship.get('affection', 0)} / 緊張度: {relationship.get('tension', 0)}",
            "キャラクター、場所、所持品、事件の気配が分かる構図にする。",
            "写真風の基準画像がある場合は写真風を維持し、急にアニメ、イラスト、絵画、3D CGへ変えない。",
            "テキスト、字幕、ロゴ、透かし、手紙やスマートフォン画面は描かない。",
        ]
        if visible_items:
            prompt_parts.append("見える所持品・装備: " + " / ".join(visible_items))
        open_threads = game.get("open_threads") or []
        if open_threads:
            prompt_parts.append("小さな伏線として入れる違和感: " + " / ".join(str(item) for item in open_threads[:2]))
        return "\n".join(prompt_parts)

    def _generate_scene_image_prompt(self, context: dict):
        request_prompt = self._build_scene_image_prompt_request(context)
        try:
            result = self._text_ai_client.generate_text(
                request_prompt,
                temperature=0.55,
                response_format={"type": "json_object"},
            )
            parsed = self._text_ai_client._try_parse_json(result.get("text"))
            if isinstance(parsed, dict):
                prompt = str(parsed.get("prompt_ja") or "").strip()
                if prompt:
                    return self._sanitize_scene_image_prompt(prompt, context)
        except Exception:
            pass
        return self._build_scene_image_prompt(context)

    def _build_scene_image_prompt_request(self, context: dict):
        state = context.get("state") or {}
        story = context.get("story") or {}
        character = context.get("character") or {}
        recent_messages = context.get("recent_messages") or []
        visible_items = self._visible_items_for_prompt(state)
        return "\n".join(
            [
                "あなたはTRPGセッション用の画像生成プロンプトを書くAIです。",
                "現在の場面を1枚のビジュアルノベル風シーン画像にするための日本語プロンプトを作ってください。",
                "Return JSON only. Required keys: prompt_ja, visual_type, subject, scene_summary.",
                "prompt_jaは画像生成AIにそのまま渡せる具体的な指示にしてください。",
                "キャラクター、場所、所持品、事件の気配、恋愛/緊張の温度感を自然に反映してください。",
                "見える所持品や装備がある場合は、誰が何を持っているかを明確にしてください。",
                "未解決スレッドは、画像内の小さな違和感や伏線として控えめに入れてください。",
                "画風基準画像がある場合、媒体、写実度、ライティング、色調、質感を維持する指示を入れてください。",
                "写真風の基準画像なら写真風を維持し、急にアニメ、イラスト、絵画、3D CGへ変えないでください。",
                "テキスト、字幕、ロゴ、透かし、手紙、封筒、スマートフォン画面は描かないでください。",
                "露骨な性的描写、裸、下着、身体部位の強調は避け、親密さは距離感、視線、手、姿勢、光で表現してください。",
                "Story:",
                json_util.dumps(story),
                "Character:",
                json_util.dumps(character),
                "Session state:",
                json_util.dumps(state),
                "World map locations:",
                json_util.dumps((context.get("world_map") or {}).get("locations") or []),
                "Visible items:",
                json_util.dumps(visible_items),
                "Recent messages:",
                json_util.dumps(recent_messages[-6:]),
            ]
        )

    def _sanitize_scene_image_prompt(self, prompt: str, context: dict):
        text = str(prompt or "").strip()
        guardrails = [
            "画像内に文字、字幕、ロゴ、透かし、手紙、封筒、スマートフォン画面を描かない。",
            "基準画像がある場合は同じ媒体、写実度、ライティング、色調、質感を維持する。",
            "急にアニメ調、イラスト調、絵画調、3D CG調へ変えない。",
        ]
        visible_items = self._visible_items_for_prompt(context.get("state") or {})
        if visible_items and "見える所持品" not in text and "装備" not in text:
            guardrails.append("見える所持品・装備: " + " / ".join(visible_items))
        return "\n".join([text, *guardrails])

    def _detect_visual_type(self, context: dict):
        state = context.get("state") or {}
        visual = state.get("visual_state") or {}
        return str(visual.get("active_visual_type") or "scene")

    def _detect_visual_subject(self, context: dict):
        state = context.get("state") or {}
        game = state.get("game_state") or {}
        visual = state.get("visual_state") or {}
        return str(visual.get("active_subject") or game.get("location") or "")
