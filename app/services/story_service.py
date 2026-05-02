from __future__ import annotations

import base64
import binascii
from datetime import datetime
import os

from flask import current_app

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..repositories.story_repository import StoryRepository
from ..repositories.story_session_repository import StorySessionRepository
from ..utils import json_util
from .asset_service import AssetService
from .character_service import CharacterService
from .closet_service import ClosetService
from .project_service import ProjectService
from .story_state_service import StoryStateService


class StoryService:
    VALID_STATUSES = {"draft", "published", "archived"}

    def __init__(
        self,
        repository: StoryRepository | None = None,
        session_repository: StorySessionRepository | None = None,
        project_service: ProjectService | None = None,
        character_service: CharacterService | None = None,
        state_service: StoryStateService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
        asset_service: AssetService | None = None,
        closet_service: ClosetService | None = None,
    ):
        self._repo = repository or StoryRepository()
        self._session_repo = session_repository or StorySessionRepository()
        self._project_service = project_service or ProjectService()
        self._character_service = character_service or CharacterService()
        self._state_service = state_service or StoryStateService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._asset_service = asset_service or AssetService()
        self._closet_service = closet_service or ClosetService()

    def list_stories(self, project_id: int, *, include_unpublished: bool = False):
        status = None if include_unpublished else "published"
        return self._repo.list_by_project(project_id, status=status)

    def get_story(self, story_id: int):
        return self._repo.get(story_id)

    def serialize_story(self, story, *, include_counts: bool = False, owner_user_id: int | None = None):
        if not story:
            return None
        character = self._character_service.get_character(story.character_id)
        thumbnail_asset = self._serialize_asset_summary(getattr(character, "thumbnail_asset_id", None) if character else None)
        base_asset = self._serialize_asset_summary(getattr(character, "base_asset_id", None) if character else None)
        default_outfit = self._closet_service.serialize_outfit(
            self._closet_service.resolve_outfit(story.character_id, getattr(story, "default_outfit_id", None))
        ) if getattr(story, "default_outfit_id", None) else None
        payload = {
            "id": story.id,
            "project_id": story.project_id,
            "character_id": story.character_id,
            "default_outfit_id": getattr(story, "default_outfit_id", None),
            "default_outfit": default_outfit,
            "created_by_user_id": story.created_by_user_id,
            "title": story.title,
            "description": story.description,
            "status": story.status,
            "story_mode": story.story_mode,
            "config_markdown": story.config_markdown,
            "config_json": self._load_json(story.config_json),
            "initial_state_json": self._load_json(story.initial_state_json),
            "style_reference_asset_id": story.style_reference_asset_id,
            "main_character_reference_asset_id": story.main_character_reference_asset_id,
            "sort_order": story.sort_order,
            "created_at": story.created_at.isoformat() if getattr(story, "created_at", None) else None,
            "updated_at": story.updated_at.isoformat() if getattr(story, "updated_at", None) else None,
            "character": (
                {
                    "id": character.id,
                    "name": character.name,
                    "nickname": getattr(character, "nickname", None),
                    "thumbnail_asset_id": getattr(character, "thumbnail_asset_id", None),
                    "base_asset_id": getattr(character, "base_asset_id", None),
                    "thumbnail_asset": thumbnail_asset,
                    "base_asset": base_asset,
                }
                if character
                else None
            ),
        }
        opening_image_asset_id = self._opening_image_asset_id(payload["config_json"])
        payload["opening_image_asset_id"] = opening_image_asset_id
        payload["opening_image_asset"] = self._serialize_asset(self._asset_service.get_asset(opening_image_asset_id)) if opening_image_asset_id else None
        if include_counts:
            sessions = self._session_repo.list_by_story(story.id)
            payload["session_count"] = len(sessions)
            if owner_user_id is not None:
                payload["my_session_count"] = len([item for item in sessions if item.owner_user_id == owner_user_id])
        return payload

    def serialize_stories(self, stories, *, include_counts: bool = False, owner_user_id: int | None = None):
        return [
            self.serialize_story(story, include_counts=include_counts, owner_user_id=owner_user_id)
            for story in stories
        ]

    def create_story(self, project_id: int, payload: dict | None, *, created_by_user_id: int):
        payload = dict(payload or {})
        if not self._project_service.get_project(project_id):
            return None
        normalized = self._normalize_payload(project_id, payload, created_by_user_id=created_by_user_id, require_all=True)
        return self._repo.create(normalized)

    def update_story(self, story_id: int, payload: dict | None):
        payload = dict(payload or {})
        story = self.get_story(story_id)
        if not story:
            return None
        if "max_turns" in payload and "config_json" not in payload:
            payload["config_json"] = story.config_json
        normalized = self._normalize_payload(
            story.project_id,
            payload,
            created_by_user_id=story.created_by_user_id,
            require_all=False,
            current_character_id=story.character_id,
        )
        if not normalized:
            raise ValueError("payload must not be empty")
        return self._repo.update(story_id, normalized)

    def delete_story(self, story_id: int):
        return self._repo.delete(story_id)

    def analyze_config(self, story_id: int, markdown: str | None = None, *, max_turns=None):
        story = self.get_story(story_id)
        if not story:
            return None
        source = str(markdown if markdown is not None else story.config_markdown or "").strip()
        config = self._analyze_markdown(source)
        config["max_turns"] = self._normalize_max_turns(max_turns or config.get("max_turns"))
        initial_state = self._build_initial_state(config, story.story_mode)
        return self._repo.update(
            story_id,
            {
                "config_markdown": source,
                "config_json": json_util.dumps(config),
                "initial_state_json": json_util.dumps(initial_state),
                "story_mode": str(config.get("story_mode") or story.story_mode or "free_chat"),
            },
        )

    def generate_markdown_draft(self, project_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        project = self._project_service.get_project(project_id)
        if not project:
            return None
        story_mode = str(payload.get("story_mode") or "dungeon_trpg").strip() or "dungeon_trpg"
        max_turns = self._normalize_max_turns(payload.get("max_turns"))
        character = None
        try:
            character_id = int(payload.get("character_id") or 0)
        except (TypeError, ValueError):
            character_id = 0
        if character_id:
            candidate = self._character_service.get_character(character_id)
            if candidate and candidate.project_id == project_id:
                character = candidate
        genre_label = self._story_mode_label(story_mode)
        character_name = getattr(character, "name", None) or "メインキャラクター"
        prompt = "\n".join(
            [
                "日本語でTRPG風ストーリー設定Markdownを作成してください。",
                "出力はMarkdown本文のみ。コードフェンス、前置き、解説は禁止。",
                "先頭行は必ず「# ストーリータイトル」にしてください。タイトルはジャンル、キャラクター、世界観からユーザーが遊びたくなる名前を作ってください。",
                f"ジャンル: {genre_label} ({story_mode})",
                f"ジャンル方針: {self._story_mode_guidance(story_mode)}",
                f"終了ターン数: {max_turns}",
                f"ワールド名: {getattr(project, 'title', '')}",
                f"ワールド説明: {getattr(project, 'summary', '') or ''}",
                f"メインキャラクター: {character_name}",
                f"キャラクター概要: {getattr(character, 'character_summary', '') if character else ''}",
                f"キャラクター性格: {getattr(character, 'personality', '') if character else ''}",
                f"キャラクター外見: {getattr(character, 'appearance_summary', '') if character else ''}",
                "必ず以下を含めてください。",
                "- タイトル",
                "- 概要",
                "- 終了ターン数",
                "- メインゴール",
                "- クリア条件",
                "- ターン進行表。指定ターン数ぴったりで、各ターンにイベント、目的、恋愛または緊張の変化を書く",
                "- イベントデッキ。手がかり、障害、アイテム、秘密、親密イベント、危険イベントを混ぜる",
                "- 選択肢方針。探索、恋愛、リスクの3択を基本にする",
                "- 画像方針。一人称視点のゲーム映えするイベントCG、選択中衣装基準を維持することを書く",
                "短すぎず、セッション中のGMがそのまま参照できる具体度にしてください。",
            ]
        )
        try:
            result = self._text_ai_client.generate_text(prompt, temperature=0.85)
            markdown = str(result.get("text") or "").strip()
        except Exception:
            markdown = ""
        if not markdown:
            markdown = self._fallback_markdown_draft(story_mode, genre_label, max_turns, character_name)
        return {
            "story_mode": story_mode,
            "max_turns": max_turns,
            "config_markdown": markdown,
        }

    def generate_opening_image(
        self,
        story_id: int,
        *,
        quality: str | None = None,
        size: str | None = None,
        model: str | None = None,
        provider: str | None = None,
    ):
        story = self.get_story(story_id)
        if not story:
            return None
        character = self._character_service.get_character(story.character_id)
        config = self._load_json(story.config_json)
        if not isinstance(config, dict):
            config = {}
        prompt = self._build_opening_image_prompt(story, character, config)
        explicit_outfit_id = getattr(story, "default_outfit_id", None)
        outfit = self._closet_service.resolve_outfit(story.character_id, getattr(story, "default_outfit_id", None))
        outfit_lines = self._closet_service.outfit_prompt_lines(outfit)
        if outfit_lines:
            prompt = "\n".join(
                [
                    prompt,
                    "Opening image reference priority:",
                    "Use the selected outfit image as the primary visual base for the character's clothing.",
                    "Do not borrow clothing from the character base image when a selected outfit reference is provided.",
                    *outfit_lines,
                ]
            )
        reference_paths = []
        reference_asset_ids = []

        def append_reference(asset_id):
            if not asset_id or int(asset_id) in {int(item) for item in reference_asset_ids}:
                return
            asset = self._asset_service.get_asset(int(asset_id))
            if asset and getattr(asset, "file_path", None):
                reference_paths.append(asset.file_path)
                reference_asset_ids.append(asset.id)

        append_reference(getattr(outfit, "asset_id", None) if outfit else None)
        base_asset_id = getattr(character, "base_asset_id", None) if character else None
        if not explicit_outfit_id:
            append_reference(base_asset_id)
        result = self._image_ai_client.generate_image(
            prompt,
            size=size or "1536x1024",
            quality=quality or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            model=model,
            provider=provider,
            output_format="png",
            background="opaque",
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("opening image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_opening_image(story.project_id, story.id, image_base64)
        asset = self._asset_service.create_asset(
            story.project_id,
            {
                "asset_type": "story_opening_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "width": 1536,
                "height": 1024,
                "metadata_json": json_util.dumps(
                    {
                        "source": "story_opening_image",
                        "story_id": story.id,
                        "quality": quality,
                        "size": "1536x1024",
                        "reference_asset_ids": reference_asset_ids,
                        "default_outfit_id": getattr(story, "default_outfit_id", None),
                        "resolved_outfit_id": getattr(outfit, "id", None) if outfit else None,
                        "revised_prompt": result.get("revised_prompt"),
                    }
                ),
            },
        )
        config.setdefault("visual_policy", {})["opening_image_asset_id"] = asset.id
        config["opening_image_asset_id"] = asset.id
        updated = self._repo.update(story.id, {"config_json": json_util.dumps(config)})
        return {
            "story": self.serialize_story(updated, include_counts=True),
            "asset": self._serialize_asset(asset),
            "quality": quality,
            "size": "1536x1024",
        }

    def register_opening_image_asset(self, story_id: int, asset_id: int):
        story = self.get_story(story_id)
        if not story:
            return None
        asset = self._asset_service.get_asset(asset_id)
        if not asset or asset.project_id != story.project_id:
            raise ValueError("asset_id is invalid")
        config = self._load_json(story.config_json)
        if not isinstance(config, dict):
            config = {}
        config.setdefault("visual_policy", {})["opening_image_asset_id"] = asset.id
        config["opening_image_asset_id"] = asset.id
        updated = self._repo.update(story.id, {"config_json": json_util.dumps(config)})
        return {
            "story": self.serialize_story(updated, include_counts=True),
            "asset": self._serialize_asset(asset),
        }

    def build_story_snapshot(self, story):
        character = self._character_service.get_character(story.character_id)
        default_outfit = self._closet_service.serialize_outfit(
            self._closet_service.resolve_outfit(story.character_id, getattr(story, "default_outfit_id", None))
        ) if getattr(story, "default_outfit_id", None) else None
        return {
            "story_id": story.id,
            "story_title": story.title,
            "story_mode": story.story_mode,
            "config_json": self._load_json(story.config_json),
            "initial_state_json": self._load_json(story.initial_state_json),
            "character_id": story.character_id,
            "character_name": character.name if character else None,
            "default_outfit_id": getattr(story, "default_outfit_id", None),
            "default_outfit_name": default_outfit.get("name") if isinstance(default_outfit, dict) else None,
            "status": story.status,
            "version_updated_at": story.updated_at.isoformat() if getattr(story, "updated_at", None) else None,
        }

    def _load_json(self, value):
        return self._state_service.load_json(value)

    def _serialize_asset(self, asset):
        if not asset:
            return None
        return {
            "id": asset.id,
            "project_id": asset.project_id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "file_path": asset.file_path,
            "mime_type": asset.mime_type,
            "file_size": asset.file_size,
            "width": asset.width,
            "height": asset.height,
            "media_url": self._build_media_url(asset.file_path),
        }

    def _serialize_asset_summary(self, asset_id: int | None):
        if not asset_id:
            return None
        return self._serialize_asset(self._asset_service.get_asset(asset_id))

    def _build_media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        if not normalized_path.startswith(normalized_root):
            return None
        return f"/media/{os.path.relpath(normalized_path, normalized_root).replace(os.sep, '/')}"

    def _normalize_payload(
        self,
        project_id: int,
        payload: dict,
        *,
        created_by_user_id: int,
        require_all: bool,
        current_character_id: int | None = None,
    ):
        normalized = {}
        if require_all or "title" in payload:
            title = str(payload.get("title") or "").strip()
            if not title:
                raise ValueError("title is required")
            normalized["title"] = title
        if require_all or "character_id" in payload:
            try:
                character_id = int(payload.get("character_id") or 0)
            except (TypeError, ValueError):
                character_id = 0
            character = self._character_service.get_character(character_id)
            if not character or character.project_id != project_id:
                raise ValueError("character_id is invalid")
            normalized["character_id"] = character_id
        effective_character_id = normalized.get("character_id") or current_character_id
        if "default_outfit_id" in payload or require_all or "character_id" in normalized:
            raw_outfit_id = payload.get("default_outfit_id")
            try:
                outfit_id = int(raw_outfit_id or 0)
            except (TypeError, ValueError):
                outfit_id = 0
            if outfit_id:
                outfit = self._closet_service.resolve_outfit(int(effective_character_id or 0), outfit_id)
                if not outfit or outfit.id != outfit_id or outfit.project_id != project_id:
                    raise ValueError("default_outfit_id is invalid")
                normalized["default_outfit_id"] = outfit_id
            else:
                normalized["default_outfit_id"] = None
        if "description" in payload or require_all:
            normalized["description"] = str(payload.get("description") or "").strip() or None
        if "status" in payload or require_all:
            status = str(payload.get("status") or "draft").strip() or "draft"
            if status not in self.VALID_STATUSES:
                raise ValueError("status is invalid")
            normalized["status"] = status
        if "story_mode" in payload or require_all:
            normalized["story_mode"] = str(payload.get("story_mode") or "free_chat").strip() or "free_chat"
        for field in ("config_markdown", "config_json", "initial_state_json"):
            if field in payload or require_all:
                normalized[field] = self._normalize_json_or_text(payload.get(field), json_field=field.endswith("_json"))
        if "max_turns" in payload or require_all:
            max_turns = self._normalize_max_turns(payload.get("max_turns"))
            config = self._load_json(normalized.get("config_json")) if normalized.get("config_json") else {}
            if not isinstance(config, dict) or not config:
                config = self._fallback_config(str(normalized.get("config_markdown") or payload.get("config_markdown") or ""))
            config["story_mode"] = normalized.get("story_mode") or config.get("story_mode") or "free_chat"
            config["max_turns"] = max_turns
            normalized["config_json"] = json_util.dumps(config)
            normalized["initial_state_json"] = json_util.dumps(self._build_initial_state(config, normalized.get("story_mode")))
        for field in ("style_reference_asset_id", "main_character_reference_asset_id"):
            if field in payload:
                normalized[field] = payload.get(field) or None
        if "sort_order" in payload:
            try:
                normalized["sort_order"] = int(payload.get("sort_order") or 0)
            except (TypeError, ValueError):
                normalized["sort_order"] = 0
        if require_all:
            normalized["project_id"] = project_id
            normalized["created_by_user_id"] = created_by_user_id
        return normalized

    def _normalize_json_or_text(self, value, *, json_field: bool):
        if value is None:
            return None
        if json_field and isinstance(value, (dict, list)):
            return json_util.dumps(value)
        return str(value).strip() or None

    def _analyze_markdown(self, markdown: str):
        if not markdown:
            return self._fallback_config(markdown)
        prompt = "\n".join(
            [
                "You convert a free-form Japanese TRPG story markdown into a compact JSON config.",
                "Return only JSON.",
                "Required keys: story_mode, max_turns, premise, main_goal, clear_conditions, tone, choice_policy, relationship_policy, event_deck, dice_policy, visual_policy.",
                "main_goal is the visible player objective. clear_conditions is an array of concrete Japanese conditions for ending/clearing the session.",
                "max_turns is the total number of turns and must be an integer from 5 to 20. If markdown specifies 終了ターン数, use it.",
                "choice_policy must include count and roles. Default roles are explore, romance, risk.",
                "event_deck must be an array of short event objects with type, name, description.",
                "Markdown:",
                markdown,
            ]
        )
        try:
            result = self._text_ai_client.generate_text(prompt, temperature=0.2, response_format={"type": "json_object"})
            parsed = self._text_ai_client._try_parse_json(result.get("text"))
            if isinstance(parsed, dict):
                return self._normalize_config(parsed, markdown)
        except Exception:
            pass
        return self._fallback_config(markdown)

    def _normalize_config(self, config: dict, markdown: str):
        normalized = dict(config)
        normalized["story_mode"] = str(normalized.get("story_mode") or "free_chat").strip() or "free_chat"
        normalized["max_turns"] = self._normalize_max_turns(normalized.get("max_turns"))
        normalized["premise"] = str(normalized.get("premise") or markdown[:500]).strip()
        normalized["main_goal"] = str(
            normalized.get("main_goal") or normalized.get("goal") or "物語の核心へたどり着く"
        ).strip()
        clear_conditions = normalized.get("clear_conditions")
        if not isinstance(clear_conditions, list):
            clear_conditions = normalized.get("goals") if isinstance(normalized.get("goals"), list) else []
        normalized["clear_conditions"] = [str(item).strip() for item in clear_conditions if str(item).strip()][:8]
        choice_policy = normalized.get("choice_policy") if isinstance(normalized.get("choice_policy"), dict) else {}
        choice_policy["count"] = int(choice_policy.get("count") or 3)
        choice_policy["roles"] = choice_policy.get("roles") if isinstance(choice_policy.get("roles"), list) else ["explore", "romance", "risk"]
        normalized["choice_policy"] = choice_policy
        normalized.setdefault("tone", [])
        normalized.setdefault("relationship_policy", {"romance_intensity": 1})
        normalized.setdefault("event_deck", [])
        normalized.setdefault("dice_policy", {"enabled": True, "visibility": "visible"})
        normalized.setdefault("visual_policy", {"use_reference_for_all_scene_images": True, "allow_style_drift": False})
        return normalized

    def _fallback_config(self, markdown: str):
        return self._normalize_config(
            {
                "story_mode": "free_chat",
                "max_turns": 10,
                "premise": markdown[:500],
                "main_goal": "物語の核心へたどり着く",
                "clear_conditions": [],
                "tone": ["adventure", "romance"],
                "choice_policy": {"count": 3, "roles": ["explore", "romance", "risk"]},
                "relationship_policy": {"romance_intensity": 1},
                "event_deck": [],
                "dice_policy": {"enabled": True, "visibility": "visible"},
                "visual_policy": {"use_reference_for_all_scene_images": True, "allow_style_drift": False},
            },
            markdown,
        )

    def _build_initial_state(self, config: dict, story_mode: str | None):
        state = self._state_service.default_state(str(config.get("story_mode") or story_mode or "free_chat"))
        initial = config.get("initial_state")
        if isinstance(initial, dict):
            for key, value in initial.items():
                if isinstance(value, dict) and isinstance(state.get(key), dict):
                    state[key].update(value)
                else:
                    state[key] = value
        goal_state = state.setdefault("goal_state", {})
        if not goal_state.get("main_goal"):
            goal_state["main_goal"] = str(config.get("main_goal") or "").strip()
        if not goal_state.get("current_goal"):
            goal_state["current_goal"] = str(config.get("current_goal") or config.get("main_goal") or "").strip()
        clear_conditions = config.get("clear_conditions")
        if isinstance(clear_conditions, list) and not goal_state.get("clear_conditions"):
            goal_state["clear_conditions"] = [str(item).strip() for item in clear_conditions if str(item).strip()]
        goal_state.setdefault("completed_goals", [])
        goal_state.setdefault("session_status", "active")
        goal_state["max_turns"] = self._normalize_max_turns(config.get("max_turns") or goal_state.get("max_turns"))
        return state

    def _normalize_max_turns(self, value):
        try:
            number = int(value or 10)
        except (TypeError, ValueError):
            number = 10
        return max(5, min(20, number))

    def _story_mode_label(self, story_mode: str):
        labels = {
            "free_chat": "自由会話",
            "dungeon_trpg": "ダンジョン探索",
            "romance_adventure": "恋愛アドベンチャー",
            "romantic_comedy": "ラブコメ",
            "comedy_adventure": "コメディ冒険",
            "daily_comedy": "日常ドタバタ",
            "school_mystery": "学園ミステリー",
            "horror_trpg": "怪異・ホラー",
            "escape_game": "脱出ゲーム",
            "isekai_adventure": "異世界冒険",
            "buddy_mission": "バディ任務",
            "mystery_trpg": "ミステリー攻略",
            "event_trpg": "イベント重視",
        }
        return labels.get(story_mode, story_mode or "ストーリー")

    def _story_mode_guidance(self, story_mode: str):
        guidance = {
            "romantic_comedy": "恋愛の期待、照れ隠し、勘違い、距離の近さ、軽い事故、ボケとツッコミで場面を動かす。ただし甘いやり取りだけで停滞させず、毎ターン事件や目的を進める。",
            "comedy_adventure": "冒険の目的は真面目に進めつつ、罠、敵、アイテム、NPCにおかしみを入れる。笑いは展開の推進力として使い、各ターンで必ず状況を変える。",
            "daily_comedy": "日常の小事件、誤解、予定外の乱入、変なルールでドタバタを起こす。キャラクターの反応で笑わせつつ、最後は関係性か目的が一歩進む構成にする。",
            "school_mystery": "学園、放課後、旧校舎、噂、秘密、友人関係を使い、調査と恋愛/緊張の揺れを混ぜる。",
            "horror_trpg": "怪異、都市伝説、追跡者、違和感を使い、怖さによる接近や助け合いを作る。過度に陰惨にせず、プレイしたくなる謎を残す。",
            "escape_game": "閉鎖空間、鍵、暗号、制限時間、協力を中心にする。各ターンで手がかりか部屋の状態が必ず変わる。",
            "isekai_adventure": "魔法、遺跡、契約、王国、運命を使う。世界の驚きとキャラクターとの絆を同時に進める。",
            "buddy_mission": "潜入、護衛、奪還、逃走などの任務を二人で攻略する。相棒感、信頼、軽口、危機での連携を重視する。",
        }
        return guidance.get(story_mode, "指定ジャンルに合わせ、目的、事件、関係性の変化、最終選択が明確な短編TRPGにする。")

    def _fallback_markdown_draft(self, story_mode: str, genre_label: str, max_turns: int, character_name: str):
        turn_lines = []
        for turn in range(1, max_turns + 1):
            if turn == 1:
                event = "導入。目的を提示し、最初の違和感を見せる。"
            elif turn == max_turns - 1:
                event = "最終選択。結末を分ける3択を提示する。"
            elif turn == max_turns:
                event = "エンディング。選択の結果を回収し、物語を完結させる。"
            else:
                event = "探索、手がかり、障害、親密イベント、危険のいずれかを必ず起こす。"
            turn_lines.append(f"- {turn}ターン目: {event}")
        return "\n".join(
            [
                f"# {genre_label}ストーリー",
                "",
                "## 概要",
                f"{character_name}と一緒に、短く濃い{genre_label}を攻略する。",
                "",
                "## 終了ターン数",
                str(max_turns),
                "",
                "## メインゴール",
                "物語の核心にたどり着き、最後の選択で結末を決める。",
                "",
                "## クリア条件",
                "- 主要な手がかりを集める",
                "- キャラクターとの信頼または親密さを深める",
                "- 最終選択で決断する",
                "",
                "## ターン進行表",
                *turn_lines,
                "",
                "## イベントデッキ",
                "- 手がかり: 小さな違和感や痕跡を発見する",
                "- 障害: 進路を阻む罠、敵、交渉が発生する",
                "- アイテム: 攻略に使える物を得る",
                "- 秘密: キャラクターまたは世界の隠し事が明らかになる",
                "- 親密: 距離が近づく場面を起こす",
                "- 危険: 緊張感が上がる事件を起こす",
                "",
                "## 選択肢方針",
                "- 毎ターン最後に探索、恋愛、リスクの3択を出す",
                "- 選択肢は必ず次の場面へ進む内容にする",
                "",
                "## 画像方針",
                "- プレイヤー一人称視点のゲーム映えするイベントCGにする",
                "- 選択中の衣装基準画像を維持する",
            ]
        )

    def _opening_image_asset_id(self, config: dict | None):
        if not isinstance(config, dict):
            return None
        visual_policy = config.get("visual_policy") if isinstance(config.get("visual_policy"), dict) else {}
        asset_id = visual_policy.get("opening_image_asset_id") or config.get("opening_image_asset_id")
        try:
            return int(asset_id) if asset_id else None
        except (TypeError, ValueError):
            return None

    def _build_opening_image_prompt(self, story, character, config: dict):
        character_name = getattr(character, "name", None) or "メインキャラクター"
        config_markdown = (story.config_markdown or "").strip()
        if len(config_markdown) > 6000:
            config_markdown = f"{config_markdown[:6000]}\n...(Markdown設定が長いため省略)"
        return "\n".join(
            [
                "ゲームのオープニング画像兼サムネイル画像を生成してください。",
                "サイズは横長1536x1024のキービジュアル。ストーリー選択画面でユーザーが押したくなるタイトルカードにする。",
                "画像内にストーリータイトルと短い帯コピーを入れる。帯コピーはMarkdown設定から魅力を抽出し、ユーザーがプレイしたくなる挑発的な1文にする。",
                "帯コピー例: 君はノアを最後まで愛せるか？ / その扉を開けたら、もう戻れない / 彼女の秘密を知っても、手を離さないか？",
                "文字は日本語で短く、読みやすく、大きめに配置する。長文、説明文、UI、字幕、看板の読める文字、透かしは入れない。",
                "プレイヤー一人称視点のゲーム映えするイベントCG。物語が始まる瞬間の期待、謎、危険、少しの恋愛感を1枚で伝える。",
                "メインキャラクターはプレイヤーの目の前、または少し先でこちらを振り返る。手を伸ばす、導く、秘密を隠す、覚悟を決めるなど、ユーザーが会いたくなる反応を入れる。",
                "ただの立ち絵、証明写真、無人背景、説明的な小物だけの画像にしない。前景、中景、背景、視線誘導、ドラマチックな光を使う。",
                "参照画像がある場合は、それを選択されたメインキャラクターの基準画像として最優先で使う。",
                "基準画像と同じ人物、顔立ち、髪型、体型、年齢感、衣装の方向性、画風、質感を維持する。別人、別衣装、別画風にしない。",
                "Markdown設定に書かれた舞台、ジャンル、ゴール、ターン進行、イベント、トーン、画像方針を反映する。",
                f"ストーリータイトル: {story.title}",
                f"画像内タイトル: {story.title}",
                "画像内帯コピー: Markdown設定から最もプレイ欲を刺激する短い1文を生成して入れる",
                f"説明: {story.description or ''}",
                f"モード: {story.story_mode}",
                f"終了ターン数: {config.get('max_turns') or ''}",
                f"メインゴール: {config.get('main_goal') or ''}",
                f"概要: {config.get('premise') or ''}",
                f"トーン: {json_util.dumps(config.get('tone') or [])}",
                f"クリア条件: {json_util.dumps(config.get('clear_conditions') or [])}",
                f"イベント候補: {json_util.dumps(config.get('event_deck') or [])}",
                f"画像方針: {json_util.dumps(config.get('visual_policy') or {})}",
                f"メインキャラクター: {character_name}",
                f"キャラクター外見: {getattr(character, 'appearance_summary', '') if character else ''}",
                f"キャラクター性格: {getattr(character, 'personality', '') if character else ''}",
                f"Markdown設定:\n{config_markdown}",
            ]
        )

    def _store_generated_opening_image(self, project_id: int, story_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated opening image payload is invalid") from exc
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        directory = os.path.join(
            current_app.config.get("STORAGE_ROOT"),
            "projects",
            str(project_id),
            "generated",
            "story_opening",
            str(story_id),
        )
        os.makedirs(directory, exist_ok=True)
        file_name = f"story_opening_{timestamp}.png"
        file_path = os.path.join(directory, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)
