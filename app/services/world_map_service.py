import base64
import os
import re
import uuid

from flask import current_app

from ..api import NotFoundError
from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..extensions import db
from ..models.chat_message import ChatMessage
from ..models.chat_session import ChatSession
from ..models.feed_post import FeedPost
from ..models.story_message import StoryMessage
from ..models.story_session import StorySession
from ..repositories.asset_repository import AssetRepository
from ..repositories.character_repository import CharacterRepository
from ..repositories.world_location_repository import WorldLocationRepository
from ..repositories.world_location_service_repository import WorldLocationServiceRepository
from ..repositories.world_map_repository import WorldMapRepository
from ..utils import json_util
from .asset_service import AssetService
from .project_service import ProjectService
from .world_service import WorldService


class WorldMapService:
    def __init__(
        self,
        location_repository: WorldLocationRepository | None = None,
        location_service_repository: WorldLocationServiceRepository | None = None,
        map_repository: WorldMapRepository | None = None,
        asset_service: AssetService | None = None,
        asset_repository: AssetRepository | None = None,
        character_repository: CharacterRepository | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        image_ai_client: ImageAIClient | None = None,
        text_ai_client: TextAIClient | None = None,
    ):
        self._locations = location_repository or WorldLocationRepository()
        self._location_services = location_service_repository or WorldLocationServiceRepository()
        self._maps = map_repository or WorldMapRepository()
        self._asset_service = asset_service or AssetService()
        self._asset_repository = asset_repository or AssetRepository()
        self._characters = character_repository or CharacterRepository()
        self._project_service = project_service or ProjectService()
        self._world_service = world_service or WorldService()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._text_ai_client = text_ai_client or TextAIClient()

    def get_overview(self, project_id: int) -> dict:
        images = self._maps.list_images(project_id)
        active_image = next((image for image in images if image.is_active == 1), None)
        return {
            "active_map_image": self.serialize_map_image(active_image),
            "map_images": [self.serialize_map_image(image) for image in images],
            "locations": self.list_locations(project_id),
        }

    def list_locations(self, project_id: int) -> list[dict]:
        return [self.serialize_location(location) for location in self._locations.list_by_project(project_id)]

    def search_locations(self, project_id: int, filters: dict | None = None) -> list[dict]:
        filters = filters or {}
        region = str(filters.get("region") or "").strip()
        location_type = str(filters.get("location_type") or "").strip()
        tag = str(filters.get("tag") or "").strip()
        search = str(filters.get("search") or "").strip().lower()
        locations = self._locations.list_by_project(project_id)
        if region:
            locations = [item for item in locations if str(item.region or "") == region]
        if location_type:
            locations = [item for item in locations if str(item.location_type or "") == location_type]
        if tag:
            locations = [item for item in locations if tag in self._tags_from_json(item.tags_json)]
        if search:
            locations = [
                item
                for item in locations
                if search in " ".join(
                    [
                        str(item.name or ""),
                        str(item.region or ""),
                        str(item.location_type or ""),
                        str(item.description or ""),
                        " ".join(self._tags_from_json(item.tags_json)),
                    ]
                ).lower()
            ]
        return [self.serialize_location(location) for location in locations]

    def get_location(self, location_id: int):
        return self._locations.get(location_id)

    def create_location(self, project_id: int, payload: dict):
        normalized = self._normalize_location_payload(payload)
        if not normalized.get("name"):
            raise ValueError("施設名は必須です。")
        location = self._locations.create(project_id, normalized)
        self.sync_location_services(location)
        return location

    def update_location(self, location_id: int, payload: dict):
        normalized = self._normalize_location_payload(payload, partial=True)
        if "name" in normalized and not normalized.get("name"):
            raise ValueError("施設名は必須です。")
        location = self._locations.update(location_id, normalized)
        if location:
            self.sync_location_services(location)
        return location

    def delete_location(self, location_id: int):
        self._location_services.delete_by_location(location_id)
        return self._locations.delete(location_id)

    def upload_location_image(self, location_id: int, upload_file):
        location = self._locations.get(location_id)
        if not location:
            raise NotFoundError()
        asset = self._asset_service.create_asset(
            location.project_id,
            {
                "asset_type": "world_location_image",
                "upload_file": upload_file,
            },
        )
        return self._locations.update(location.id, {"image_asset_id": asset.id})

    def generate_location_image(self, location_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        location = self._locations.get(location_id)
        if not location:
            raise NotFoundError()
        owner = self._resolve_location_owner(location)
        prompt = self._build_location_image_prompt(location, owner=owner)
        reference_paths = self._location_reference_image_paths(owner)
        size = payload.get("size") or "1536x1024"
        quality = payload.get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium")
        result = self._image_ai_client.generate_image(
            prompt,
            size=size,
            quality=quality,
            model=payload.get("model") or payload.get("image_ai_model"),
            provider=payload.get("provider") or payload.get("image_ai_provider"),
            output_format="png",
            background="opaque",
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("location image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_location_image(
            project_id=location.project_id,
            location_id=location.id,
            image_base64=image_base64,
        )
        asset = self._asset_service.create_asset(
            location.project_id,
            {
                "asset_type": "world_location_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "world_location_image_generation",
                        "location_id": location.id,
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "model": result.get("model"),
                        "quality": result.get("quality") or quality,
                        "size": size,
                        "reference_character_id": getattr(owner, "id", None),
                        "reference_image_count": result.get("reference_image_count") or len(reference_paths),
                        "operation": result.get("operation"),
                    }
                ),
            },
        )
        return self._locations.update(location.id, {"image_asset_id": asset.id})

    def sync_location_services(self, location):
        if not location:
            return []
        generated = self._generate_location_service_candidates(location)
        if not generated:
            self._location_services.archive_missing(location.id, set())
            return []
        existing = {
            self._normalize_service_name(item.name): item
            for item in self._location_services.list_by_location(location.id, include_archived=True)
        }
        kept_ids: set[int] = set()
        synced = []
        for index, item in enumerate(generated):
            name = self._normalize_service_name(item.get("name"))
            if not name:
                continue
            payload = {
                "name": name[:255],
                "service_type": str(item.get("service_type") or item.get("type") or "施設内サービス").strip()[:100],
                "summary": self._shorten(str(item.get("summary") or "").strip(), 1800),
                "chat_hook": self._shorten(str(item.get("chat_hook") or "").strip(), 1200),
                "visual_prompt": self._shorten(str(item.get("visual_prompt") or "").strip(), 1600),
                "status": "published",
                "sort_order": index,
            }
            existing_row = existing.get(name)
            if existing_row:
                row = self._location_services.update(existing_row.id, payload)
            else:
                row = self._location_services.create(location.project_id, location.id, payload)
            if row:
                kept_ids.add(row.id)
                synced.append(row)
        self._location_services.archive_missing(location.id, kept_ids)
        return synced

    def _generate_location_service_candidates(self, location) -> list[dict]:
        description = str(getattr(location, "description", "") or "").strip()
        if len(description) < 80:
            return []
        prompt = (
            "施設説明から、チャット中に選択できる施設内サービス・店舗・アトラクション・区画・イベントを抽出してください。\n"
            "大きな施設そのものではなく、ユーザーがその施設内で次に選びたくなる具体的な行き先や体験に分解します。\n\n"
            "重要ルール:\n"
            "- 架空設定を勝手に増やしすぎず、説明文に根拠があるものを優先する。\n"
            "- 名前は短く、ボタンに出して分かりやすいものにする。\n"
            "- summary はキャラクターが理解するための概要。\n"
            "- chat_hook は会話が盛り上がる使い方、感情、事件の火種を書く。\n"
            "- visual_prompt は画像生成に使える視覚要素を日本語で具体的に書く。文字や看板の可読文字は要求しない。\n"
            "- 最大8件。なければ空配列。\n"
            "- JSONのみ返す。形式: {\"services\":[{\"name\":\"...\",\"service_type\":\"...\",\"summary\":\"...\",\"chat_hook\":\"...\",\"visual_prompt\":\"...\"}]}\n\n"
            f"施設名: {getattr(location, 'name', '') or ''}\n"
            f"施設種別: {getattr(location, 'location_type', '') or ''}\n"
            f"地域: {getattr(location, 'region', '') or ''}\n"
            f"施設説明:\n{description[:6000]}"
        )
        try:
            result = self._text_ai_client.extract_state_json(prompt)
            parsed = result.get("parsed_json") or {}
        except Exception:
            current_app.logger.exception("location service extraction failed")
            return []
        services = parsed.get("services") if isinstance(parsed, dict) else None
        if not isinstance(services, list):
            return []
        return [item for item in services if isinstance(item, dict)][:8]

    def _normalize_service_name(self, value) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip())

    def upload_map_image(self, project_id: int, upload_file, user_id: int | None = None):
        asset = self._asset_service.create_asset(
            project_id,
            {
                "asset_type": "world_map_image",
                "upload_file": upload_file,
            },
        )
        title = os.path.splitext(asset.file_name or "")[0] or "ワールドマップ"
        return self._maps.create_image(
            project_id,
            {
                "asset_id": asset.id,
                "title": title[:255],
                "source_type": "upload",
                "created_by_user_id": user_id,
            },
        )

    def generate_map_image(self, project_id: int, payload: dict | None = None, user_id: int | None = None):
        payload = dict(payload or {})
        project = self._project_service.get_project(project_id)
        if not project:
            raise NotFoundError()
        prompt = self._build_map_image_prompt(project_id)
        size = payload.get("size") or "1536x1024"
        quality = payload.get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium")
        result = self._image_ai_client.generate_image(
            prompt,
            size=size,
            quality=quality,
            model=payload.get("model") or payload.get("image_ai_model"),
            provider=payload.get("provider") or payload.get("image_ai_provider"),
            output_format="png",
            background="opaque",
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("world map image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_map_image(
            project_id=project_id,
            image_base64=image_base64,
        )
        asset = self._asset_service.create_asset(
            project_id,
            {
                "asset_type": "world_map_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "world_map_image_generation",
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "model": result.get("model"),
                        "quality": result.get("quality") or quality,
                        "size": size,
                    }
                ),
            },
        )
        return self._maps.create_image(
            project_id,
            {
                "asset_id": asset.id,
                "title": f"{project.title or 'ワールド'} 俯瞰図",
                "prompt_text": prompt,
                "source_type": "generated",
                "quality": result.get("quality") or quality,
                "size": size,
                "is_active": True,
                "created_by_user_id": user_id,
            },
        )

    def extract_location_candidates(self, project_id: int, limit: int = 24) -> list[dict]:
        existing_names = {str(item.name or "").strip() for item in self._locations.list_by_project(project_id)}
        candidates: dict[str, dict] = {}
        for source_type, source_id, text in self._candidate_source_texts(project_id):
            for name in self._extract_location_names(text):
                if name in existing_names:
                    continue
                candidate = candidates.setdefault(
                    name,
                    {
                        "name": name,
                        "location_type": self._guess_location_type(name, text),
                        "description": "",
                        "source_note": "",
                        "sources": [],
                        "_evidence": [],
                    },
                )
                candidate["sources"].append({"source_type": source_type, "source_id": source_id})
                evidence = self._candidate_evidence(name, text)
                if evidence and evidence not in candidate["_evidence"]:
                    candidate["_evidence"].append(evidence)
                if candidate["location_type"] == "施設":
                    candidate["location_type"] = self._guess_location_type(name, text)
        prepared = []
        for candidate in candidates.values():
            candidate["description"] = self._candidate_description(
                candidate["name"],
                candidate["_evidence"],
                candidate["location_type"],
            )
            candidate["source_note"] = self._candidate_source_note(candidate["sources"])
            prepared.append(candidate)
        prepared = self._refine_location_candidates_with_ai(project_id, prepared)
        for candidate in prepared:
            candidate.pop("_evidence", None)
        return sorted(prepared, key=lambda item: len(item["sources"]), reverse=True)[: max(1, min(int(limit or 24), 60))]

    def generate_location_draft(self, project_id: int, payload: dict | None = None) -> dict:
        payload = dict(payload or {})
        current_location = payload.get("current_location") if isinstance(payload.get("current_location"), dict) else payload
        prompt = self._build_location_draft_prompt(project_id, current_location)
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.75,
            response_format={"type": "json_object"},
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("location draft response is invalid")
        return self._normalize_location_draft(parsed, current_location)

    def related_sources(self, location_id: int, limit: int = 20) -> dict:
        location = self._locations.get(location_id)
        if not location:
            raise NotFoundError()
        keyword = str(location.name or "").strip()
        if not keyword:
            return {"feed_posts": [], "chat_messages": [], "story_messages": []}
        limit = max(1, min(int(limit or 20), 80))
        feed_posts = (
            FeedPost.query.filter(
                FeedPost.project_id == location.project_id,
                FeedPost.deleted_at.is_(None),
                FeedPost.body.ilike(f"%{keyword}%"),
            )
            .order_by(FeedPost.id.desc())
            .limit(limit)
            .all()
        )
        chat_messages = (
            db.session.query(ChatMessage, ChatSession)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .filter(ChatSession.project_id == location.project_id, ChatMessage.message_text.ilike(f"%{keyword}%"))
            .order_by(ChatMessage.id.desc())
            .limit(limit)
            .all()
        )
        story_messages = (
            db.session.query(StoryMessage, StorySession)
            .join(StorySession, StorySession.id == StoryMessage.session_id)
            .filter(
                StorySession.project_id == location.project_id,
                StoryMessage.deleted_at.is_(None),
                StoryMessage.message_text.ilike(f"%{keyword}%"),
            )
            .order_by(StoryMessage.id.desc())
            .limit(limit)
            .all()
        )
        return {
            "feed_posts": [
                {"id": row.id, "body": self._shorten(row.body, 180), "status": row.status, "created_at": row.created_at.isoformat() if row.created_at else None}
                for row in feed_posts
            ],
            "chat_messages": [
                {
                    "id": message.id,
                    "session_id": session.id,
                    "speaker_name": message.speaker_name,
                    "message_text": self._shorten(message.message_text, 180),
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                }
                for message, session in chat_messages
            ],
            "story_messages": [
                {
                    "id": message.id,
                    "session_id": session.id,
                    "speaker_name": message.speaker_name,
                    "message_text": self._shorten(message.message_text, 180),
                    "created_at": message.created_at.isoformat() if message.created_at else None,
                }
                for message, session in story_messages
            ],
        }

    def select_map_image(self, project_id: int, image_id: int):
        return self._maps.set_active(project_id, image_id)

    def delete_map_image(self, project_id: int, image_id: int):
        return self._maps.delete_image(project_id, image_id)

    def location_prompt_context(self, project_id: int, limit: int = 12) -> str:
        locations = self._locations.list_by_project(project_id)[:limit]
        if not locations:
            return ""
        lines = ["World map locations:"]
        for location in locations:
            parts = [f"- {location.name or ''}"]
            if getattr(location, "region", None):
                parts.append(f"region: {location.region}")
            if location.location_type:
                parts.append(f"type: {location.location_type}")
            tags = self._tags_from_json(getattr(location, "tags_json", None))
            if tags:
                parts.append(f"tags: {', '.join(tags)}")
            if location.description:
                parts.append(f"description: {self._shorten(location.description, 220)}")
            owner = self._characters.get(location.owner_character_id) if location.owner_character_id else None
            if owner:
                parts.append(f"owner: {owner.name}")
            lines.append(" / ".join(parts))
        return "\n".join(lines)

    def serialize_location(self, location):
        if not location:
            return None
        owner = self._characters.get(location.owner_character_id) if location.owner_character_id else None
        return {
            "id": location.id,
            "project_id": location.project_id,
            "name": location.name,
            "region": getattr(location, "region", None),
            "location_type": location.location_type,
            "tags": self._tags_from_json(getattr(location, "tags_json", None)),
            "tags_text": "\n".join(self._tags_from_json(getattr(location, "tags_json", None))),
            "description": location.description,
            "owner_character_id": location.owner_character_id,
            "owner_character_name": getattr(owner, "name", None),
            "image_asset_id": location.image_asset_id,
            "image_asset": self._serialize_asset(location.image_asset_id),
            "services": [
                self.serialize_location_service(item)
                for item in self._location_services.list_by_location(location.id)
            ],
            "source_type": location.source_type,
            "source_note": location.source_note,
            "status": location.status,
            "sort_order": location.sort_order,
            "created_at": location.created_at.isoformat() if location.created_at else None,
            "updated_at": location.updated_at.isoformat() if location.updated_at else None,
        }

    def serialize_location_service(self, service):
        if not service:
            return None
        return {
            "id": service.id,
            "location_id": service.location_id,
            "project_id": service.project_id,
            "name": service.name,
            "service_type": service.service_type,
            "summary": service.summary,
            "chat_hook": service.chat_hook,
            "visual_prompt": service.visual_prompt,
            "status": service.status,
            "sort_order": service.sort_order,
            "created_at": service.created_at.isoformat() if service.created_at else None,
            "updated_at": service.updated_at.isoformat() if service.updated_at else None,
        }

    def serialize_map_image(self, image):
        if not image:
            return None
        return {
            "id": image.id,
            "project_id": image.project_id,
            "asset_id": image.asset_id,
            "asset": self._serialize_asset(image.asset_id),
            "title": image.title,
            "description": image.description,
            "source_type": image.source_type,
            "quality": image.quality,
            "size": image.size,
            "is_active": image.is_active == 1,
            "created_at": image.created_at.isoformat() if image.created_at else None,
            "updated_at": image.updated_at.isoformat() if image.updated_at else None,
        }

    def _serialize_asset(self, asset_id: int | None):
        if not asset_id:
            return None
        asset = self._asset_repository.get(asset_id)
        if not asset:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "media_url": self._build_media_url(asset.file_path),
            "mime_type": asset.mime_type,
            "width": asset.width,
            "height": asset.height,
        }

    def _build_media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        try:
            if os.path.commonpath([normalized_path, normalized_root]) != normalized_root:
                return None
        except ValueError:
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"

    def _normalize_location_payload(self, payload: dict, partial: bool = False) -> dict:
        normalized = {}
        fields = {
            "name",
            "region",
            "location_type",
            "tags",
            "tags_text",
            "tags_json",
            "description",
            "owner_character_id",
            "image_asset_id",
            "source_type",
            "source_note",
            "status",
            "sort_order",
        }
        for field in fields:
            if field in payload:
                normalized[field] = payload.get(field)
        if not partial and "status" not in normalized:
            normalized["status"] = "published"
        if "name" in normalized:
            normalized["name"] = str(normalized.get("name") or "").strip()
        if "tags_text" in normalized and "tags_json" not in normalized:
            normalized["tags_json"] = json_util.dumps(self._normalize_tags(normalized.pop("tags_text")))
        if "tags" in normalized and "tags_json" not in normalized:
            normalized["tags_json"] = json_util.dumps(self._normalize_tags(normalized.pop("tags")))
        for field in ("region", "location_type", "description", "source_type", "source_note", "status"):
            if field in normalized:
                value = normalized.get(field)
                normalized[field] = str(value).strip() if value not in (None, "") else None
        for field in ("owner_character_id", "image_asset_id"):
            if field in normalized:
                normalized[field] = self._int_or_none(normalized.get(field))
        if "sort_order" in normalized:
            normalized["sort_order"] = int(normalized.get("sort_order") or 0)
        if not partial and not normalized.get("source_type"):
            normalized["source_type"] = "manual"
        if not partial and not normalized.get("status"):
            normalized["status"] = "published"
        return normalized

    def _int_or_none(self, value):
        if value in (None, ""):
            return None
        return int(value)

    def _shorten(self, value, limit: int):
        text = str(value or "").strip().replace("\r\n", "\n")
        return text if len(text) <= limit else text[:limit].rstrip() + "..."

    def _build_location_draft_prompt(self, project_id: int, current_location: dict | None = None) -> str:
        current_location = current_location if isinstance(current_location, dict) else {}
        project = self._project_service.get_project(project_id)
        world = self._world_service.get_world(project_id)
        existing_locations = self._locations.list_by_project(project_id)[:40]
        characters = self._characters.list_by_project(project_id)[:60]
        lines = [
            "Return only JSON.",
            "Create or improve one facility/location draft for a Japanese character live chat and novel-game tool.",
            "The user may have typed only a rough idea. Preserve the user's intent and expand it into a concrete facility that characters can understand and act in.",
            "Required JSON keys: name, region, location_type, tags_text, description, source_note.",
            "All values must be Japanese strings. tags_text should be newline-separated short tags.",
            "description must be detailed enough to support chat location movement, service extraction, and image generation.",
            "In description, include the facility role, atmosphere, who visits it, what characters can do there, notable rooms/services/attractions, sensory details, and hooks for conversation.",
            "Do not invent unrelated characters. If you mention characters, prefer the registered characters listed below.",
            "Avoid generic filler. Make the facility specific, playable, and easy to turn into selectable services.",
            "",
            "Current form input:",
        ]
        for key in ("name", "location_type", "region", "owner_character_id", "tags_text", "description", "source_note"):
            lines.append(f"{key}: {current_location.get(key) or ''}")
        if project:
            lines.extend(
                [
                    "",
                    "Project:",
                    f"title: {getattr(project, 'title', '') or ''}",
                    f"summary: {getattr(project, 'summary', '') or ''}",
                ]
            )
        if world:
            lines.extend(
                [
                    "",
                    "World setting:",
                    f"name: {getattr(world, 'name', '') or ''}",
                    f"tone: {getattr(world, 'tone', '') or ''}",
                    f"era: {getattr(world, 'era_description', '') or ''}",
                    f"overview: {getattr(world, 'overview', '') or ''}",
                    f"technology: {getattr(world, 'technology_level', '') or ''}",
                    f"social_structure: {getattr(world, 'social_structure', '') or ''}",
                    f"important_facilities: {getattr(world, 'rules_json', '') or ''}",
                    f"forbidden: {getattr(world, 'forbidden_json', '') or ''}",
                ]
            )
        if characters:
            lines.append("")
            lines.append("Registered characters to prefer when relevant:")
            for character in characters:
                lines.append(
                    "- "
                    + " / ".join(
                        [
                            f"id: {character.id}",
                            f"name: {character.name or ''}",
                            f"nickname: {character.nickname or ''}",
                            f"summary: {self._shorten(getattr(character, 'character_summary', '') or getattr(character, 'personality', ''), 180)}",
                        ]
                    )
                )
        if existing_locations:
            lines.append("")
            lines.append("Existing registered facilities. Avoid duplicating these unless the current input clearly edits one:")
            for location in existing_locations:
                lines.append(
                    "- "
                    + " / ".join(
                        [
                            f"name: {location.name or ''}",
                            f"type: {location.location_type or ''}",
                            f"region: {getattr(location, 'region', '') or ''}",
                            f"description: {self._shorten(location.description, 180)}",
                        ]
                    )
                )
        return "\n".join(lines)

    def _normalize_location_draft(self, parsed: dict, current_location: dict | None = None) -> dict:
        current_location = current_location if isinstance(current_location, dict) else {}
        defaults = {
            "name": current_location.get("name") or "未設定の施設",
            "region": current_location.get("region") or "",
            "location_type": current_location.get("location_type") or "施設",
            "tags_text": current_location.get("tags_text") or "",
            "description": current_location.get("description") or "",
            "source_note": current_location.get("source_note") or "AI補完",
        }
        draft = {}
        for key, default in defaults.items():
            value = parsed.get(key, default)
            if key == "tags_text" and isinstance(value, list):
                value = "\n".join(str(item).strip() for item in value if str(item or "").strip())
            draft[key] = self._shorten(str(value or default).strip(), 5000 if key == "description" else 1200)
        if current_location.get("owner_character_id") not in (None, ""):
            draft["owner_character_id"] = current_location.get("owner_character_id")
        if current_location.get("sort_order") not in (None, ""):
            draft["sort_order"] = current_location.get("sort_order")
        return draft

    def _normalize_tags(self, value) -> list[str]:
        if isinstance(value, list):
            raw_items = value
        else:
            raw_items = re.split(r"[\n,、]+", str(value or ""))
        tags = []
        seen = set()
        for item in raw_items:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            tags.append(text[:40])
        return tags[:20]

    def _tags_from_json(self, value) -> list[str]:
        if not value:
            return []
        try:
            parsed = json_util.loads(value) if isinstance(value, str) else value
        except Exception:
            parsed = []
        return self._normalize_tags(parsed)

    def _candidate_source_texts(self, project_id: int):
        rows = []
        for post in (
            FeedPost.query.filter(FeedPost.project_id == project_id, FeedPost.deleted_at.is_(None))
            .order_by(FeedPost.id.desc())
            .limit(80)
            .all()
        ):
            rows.append(("Feed", post.id, post.body or ""))
        for message, session in (
            db.session.query(ChatMessage, ChatSession)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .filter(ChatSession.project_id == project_id)
            .order_by(ChatMessage.id.desc())
            .limit(120)
            .all()
        ):
            rows.append(("チャット", message.id, message.message_text or ""))
        for message, session in (
            db.session.query(StoryMessage, StorySession)
            .join(StorySession, StorySession.id == StoryMessage.session_id)
            .filter(StorySession.project_id == project_id, StoryMessage.deleted_at.is_(None))
            .order_by(StoryMessage.id.desc())
            .limit(120)
            .all()
        ):
            rows.append(("ストーリー", message.id, message.message_text or ""))
        return rows

    def _extract_location_names(self, text: str) -> list[str]:
        value = str(text or "")
        candidates = []
        suffixes = (
            "ランド", "銀行", "バンク", "証券", "ローン", "公園", "広場", "市場", "タワー", "カジノ",
            "クラブ", "寺", "寺院", "僧院", "資料庫", "記録館", "研究所", "開発局", "会社", "店",
            "喫茶店", "予備校", "学校", "村", "街", "都市", "回廊", "通路", "屋台", "温室", "水族館",
            "観測塔", "取引所", "区画",
        )
        pattern = r"([一-龥ァ-ヶーA-Za-z0-9・]{2,24}(?:" + "|".join(re.escape(item) for item in suffixes) + r"))"
        for match in re.findall(pattern, value):
            name = match.strip("「」『』（）()、。，. ")
            if len(name) < 2 or name in candidates or self._is_noise_location_name(name):
                continue
            candidates.append(name)
        return candidates[:8]

    def _is_noise_location_name(self, name: str) -> bool:
        value = str(name or "").strip()
        noise_suffixes = ("ドローン", "データ鍵", "選択肢", "ログ", "メッセージ")
        noise_words = ("ほか", "する公開裁判", "数字だけで返して")
        return value.endswith(noise_suffixes) or any(word in value for word in noise_words)

    def _guess_location_type(self, name: str, text: str) -> str:
        lookup = {
            "バンク": "金融機関",
            "銀行": "金融機関",
            "証券": "金融機関",
            "ローン": "金融機関",
            "ランド": "娯楽施設",
            "カジノ": "娯楽施設",
            "クラブ": "娯楽施設",
            "タワー": "ランドマーク",
            "広場": "公共空間",
            "公園": "公園",
            "市場": "商業施設",
            "店": "商業施設",
            "屋台": "商業施設",
            "寺": "宗教施設",
            "僧院": "宗教施設",
            "研究所": "研究施設",
            "開発局": "行政/研究施設",
            "予備校": "教育施設",
            "学校": "教育施設",
            "村": "集落",
            "街": "地域",
            "回廊": "通路/区域",
            "通路": "通路/区域",
            "区画": "区域",
            "観測塔": "施設",
            "取引所": "金融機関",
        }
        for key, label in lookup.items():
            if key in name:
                return label
        return "施設"

    def _candidate_source_note(self, sources: list[dict]) -> str:
        if not sources:
            return ""
        counts: dict[str, int] = {}
        first_by_type: dict[str, int] = {}
        for source in sources:
            source_type = str(source.get("source_type") or "出典")
            source_id = source.get("source_id")
            counts[source_type] = counts.get(source_type, 0) + 1
            first_by_type.setdefault(source_type, source_id)
        parts = []
        for source_type, count in sorted(counts.items(), key=lambda item: item[1], reverse=True):
            label = f"{source_type} {first_by_type.get(source_type)}"
            if count > 1:
                label = f"{label} ほか{count - 1}件"
            parts.append(label)
        return " / ".join(parts[:3])

    def _refine_location_candidates_with_ai(self, project_id: int, candidates: list[dict]) -> list[dict]:
        if not candidates:
            return candidates
        project = self._project_service.get_project(project_id)
        world = self._world_service.get_world(project_id)
        compact_candidates = []
        for candidate in candidates[:16]:
            compact_candidates.append(
                {
                    "name": candidate.get("name"),
                    "location_type": candidate.get("location_type") or "施設",
                    "source_note": candidate.get("source_note"),
                    "draft_description": candidate.get("description"),
                    "evidence": [self._shorten(item, 420) for item in candidate.get("_evidence", [])[:5]],
                }
            )
        prompt = (
            "以下は、架空世界のFeed・チャット・ストーリーから抽出した施設候補です。\n"
            "各候補について、人間が読むための施設概要 description を作ってください。\n\n"
            "重要ルール:\n"
            "- description は日本語。短くまとめすぎず、施設の雰囲気、役割、誰が訪れるか、物語での使いどころ、視覚的特徴が分かるように詳しく書く。\n"
            "- description は出典の事実から自然に統合する。会話ログをそのまま貼らず、設定資料として読める文章にする。\n"
            "- 画像生成用プロンプトではない。施設の設定資料として自然な文章にする。\n"
            "- JSONのみ返す。形式: {\"locations\":[{\"name\":\"...\",\"description\":\"...\"}]}\n\n"
            f"Project: {getattr(project, 'title', '') or ''}\n"
            f"World overview: {getattr(world, 'overview', '') or ''}\n"
            f"World tone: {getattr(world, 'tone', '') or ''}\n"
            f"Candidates JSON:\n{json_util.dumps(compact_candidates)}"
        )
        try:
            result = self._text_ai_client.extract_state_json(prompt)
            parsed = result.get("parsed_json") or {}
        except Exception:
            return candidates
        rows = parsed.get("locations") if isinstance(parsed, dict) else None
        if not isinstance(rows, list):
            return candidates
        by_name = {
            str(row.get("name") or "").strip(): row
            for row in rows
            if isinstance(row, dict) and str(row.get("name") or "").strip()
        }
        for candidate in candidates:
            row = by_name.get(str(candidate.get("name") or "").strip())
            if not row:
                continue
            description = str(row.get("description") or "").strip()
            if description:
                candidate["description"] = description[:4000]
        return candidates

    def _candidate_evidence(self, name: str, text: str) -> str:
        value = str(text or "").replace("\r\n", "\n").strip()
        index = value.find(name)
        if index < 0:
            return self._clean_candidate_text(value)
        start = max(0, index - 120)
        end = min(len(value), index + len(name) + 260)
        return self._clean_candidate_text(value[start:end])

    def _clean_candidate_text(self, value: str) -> str:
        text = str(value or "").replace("\r\n", "\n")
        text = re.sub(r"#\S+", "", text)
        text = re.sub(r"^■.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"「[0-9１-９]\s*[^」]{0,60}」", "", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{2,}", "\n", text)
        return text.strip(" \n、。，.「」『』")

    def _candidate_description(self, name: str, evidence_items: list[str], location_type: str | None = None) -> str:
        sentences = []
        for evidence in evidence_items:
            sentences.extend(self._candidate_sentences(name, evidence))
        if not sentences:
            return f"{name}に関する施設候補です。関連する投稿や会話から詳細を確認してください。"

        primary = sentences[0]
        related = [item for item in sentences[1:] if item != primary][:5]
        description = self._compose_candidate_description(name, primary, related, location_type)
        return self._shorten(description, 900)

    def _candidate_sentences(self, name: str, text: str) -> list[str]:
        cleaned = self._clean_candidate_text(text)
        fragments = [
            item.strip(" \n、。，.「」『』")
            for item in re.split(r"(?<=[。！？!?])|\n+", cleaned)
            if item.strip(" \n、。，.「」『』")
        ]
        selected = []
        for index, fragment in enumerate(fragments):
            if name not in fragment:
                continue
            selected.append(fragment)
            if index + 1 < len(fragments) and name not in fragments[index + 1]:
                selected.append(fragments[index + 1].strip(" \n、。，.「」『』"))
            if index + 2 < len(fragments) and name not in fragments[index + 2]:
                selected.append(fragments[index + 2].strip(" \n、。，.「」『』"))
        if not selected and cleaned:
            selected.append(cleaned)
        unique = []
        seen = set()
        for item in selected:
            item = self._shorten(item, 220)
            if item and item not in seen:
                seen.add(item)
                unique.append(item)
        return unique[:8]

    def _compose_candidate_description(
        self,
        name: str,
        primary: str,
        related: list[str] | None = None,
        location_type: str | None = None,
    ) -> str:
        primary = primary.strip()
        related = [item.strip() for item in (related or []) if str(item or "").strip()]
        primary = re.sub(r"^[^。\n：:]{1,16}[：:]", "", primary).strip()
        related = [re.sub(r"^[^。\n：:]{1,16}[：:]", "", item).strip() for item in related]
        if primary.startswith(name):
            base = primary
        elif f"{name}の" in primary or f"{name}に" in primary or f"{name}へ" in primary:
            base = primary
        else:
            base = f"{name}は、{primary}"
        if not base.endswith(("。", "！", "？", "!", "?")):
            base += "。"
        additions = []
        for item in related:
            if not item or item in base or item in additions:
                continue
            if not item.endswith(("。", "！", "？", "!", "?")):
                item += "。"
            additions.append(item)
        if additions:
            base += "".join(additions[:4])
        if location_type and location_type != "施設":
            base += f" ワールドマップ上では「{location_type}」として扱い、外観画像では周辺環境、入口、照明、訪れる人物の動線が分かるように描くと使いやすい。"
        else:
            base += " 外観画像では施設の入口、周辺環境、象徴的な構造、照明、訪れる人物の動線が分かるように描くと使いやすい。"
        return base

    def _resolve_location_owner(self, location):
        if getattr(location, "owner_character_id", None):
            return self._characters.get(location.owner_character_id)
        haystack = " ".join(
            [
                str(location.name or ""),
                str(getattr(location, "region", "") or ""),
                str(location.location_type or ""),
                str(location.description or ""),
                str(location.source_note or ""),
            ]
        )
        for character in self._characters.list_by_project(location.project_id):
            names = [character.name, character.nickname]
            if any(name and str(name).strip() and str(name).strip() in haystack for name in names):
                return character
        return None

    def _location_reference_image_paths(self, owner) -> list[str]:
        if not owner or not getattr(owner, "base_asset_id", None):
            return []
        asset = self._asset_repository.get(owner.base_asset_id)
        if not asset or not asset.file_path or not os.path.exists(asset.file_path):
            return []
        return [asset.file_path]

    def _build_location_image_prompt(self, location, *, owner=None) -> str:
        project = self._project_service.get_project(location.project_id)
        world = self._world_service.get_world(location.project_id)
        owner = owner or self._resolve_location_owner(location)
        generated_visual_prompt = self._generate_location_visual_prompt(location, project, world, owner)
        lines = [
            "Create a polished key visual image of a fictional world location for a character live chat / TRPG setting.",
            "The default composition must be an exterior view from outside the facility: facade, entrance, surrounding streets/plaza/landscape, skyline, and atmosphere.",
            "Show the place itself as the main subject: exterior architecture, entrance design, silhouette, lighting, and memorable visual details.",
            "Avoid interior rooms unless the location description explicitly requires an interior-only place.",
            "Do not include readable text, letters, subtitles, captions, UI, logos, or watermarks.",
            "Avoid making it look like a generic stock photo. Make it specific, story-rich, and usable as a location card thumbnail.",
            "Use a wide cinematic composition, 1536x1024 landscape framing, clear focal point, beautiful lighting, high production value.",
            "Use the automatically generated visual direction below as the primary scene prompt.",
            generated_visual_prompt,
            f"Location name: {location.name or ''}",
            f"Location type: {location.location_type or ''}",
            f"Location description: {location.description or ''}",
            f"World/project name: {getattr(project, 'title', '') or ''}",
            f"World/project summary: {getattr(project, 'summary', '') or ''}",
        ]
        if world:
            lines.extend(
                [
                    f"World tone: {world.tone or ''}",
                    f"Era: {world.era_description or ''}",
                    f"World overview: {world.overview or ''}",
                    f"Technology level: {world.technology_level or ''}",
                    f"Social structure: {world.social_structure or ''}",
                    f"Important facilities/rules: {world.rules_json or ''}",
                    f"Forbidden settings to avoid: {world.forbidden_json or ''}",
                ]
            )
        if owner:
            lines.extend(
                [
                    "This facility is associated with the following character. Include that character in the scene when a reference image is provided.",
                    "Keep the exterior facility as the main subject, but place the character naturally in the foreground or near the entrance, as if they are welcoming the visitor, arriving, guarding, or presenting the place.",
                    "Preserve the character identity, face, hair, body impression, outfit direction, and art style from the reference image as much as possible.",
                    "Do not turn the image into a character portrait. The viewer should still understand the facility exterior at a glance.",
                    f"Owner character: {owner.name or ''}",
                    f"Owner nickname: {owner.nickname or ''}",
                    f"Owner personality: {owner.personality or ''}",
                    f"Owner visual style: {owner.appearance_summary or ''}",
                    f"Owner art style: {owner.art_style or ''}",
                ]
            )
        return "\n".join(lines)

    def _generate_location_visual_prompt(self, location, project=None, world=None, owner=None) -> str:
        base_prompt = self._fallback_location_visual_prompt(location, project, world, owner)
        prompt = (
            "以下の施設設定から、画像生成AIに渡すための具体的なビジュアルプロンプトを1つ作成してください。\n"
            "入力欄に保存されたプロンプトは使わず、施設の説明・世界観・キャラクター情報からその場で作ります。\n\n"
            "ルール:\n"
            "- 基本は外から見たエクステリア。外観、入口、周辺環境、光、空気感、ランドマーク性を具体的に書く。\n"
            "- 施設がキャラクターにまつわる場合、施設を主役にしたまま、キャラクターを入口付近や前景に自然に配置する。\n"
            "- キャラクター参照画像が渡される前提なら、顔、髪、衣装、画風を保つ指示を含める。\n"
            "- readable text, captions, UI, logos, watermarks を避ける指示を含める。\n"
            "- 1536x1024の横長キービジュアルとして使いやすい構図にする。\n"
            "- 返答はプロンプト本文のみ。説明やJSONは不要。\n\n"
            f"Project: {getattr(project, 'title', '') or ''}\n"
            f"World overview: {getattr(world, 'overview', '') or ''}\n"
            f"World tone: {getattr(world, 'tone', '') or ''}\n"
            f"Location name: {location.name or ''}\n"
            f"Location type: {location.location_type or ''}\n"
            f"Location description: {location.description or ''}\n"
            f"Owner character: {getattr(owner, 'name', '') or ''}\n"
            f"Owner nickname: {getattr(owner, 'nickname', '') or ''}\n"
            f"Owner personality: {getattr(owner, 'personality', '') or ''}\n"
            f"Owner appearance: {getattr(owner, 'appearance_summary', '') or ''}\n"
            f"Owner art style: {getattr(owner, 'art_style', '') or ''}"
        )
        try:
            result = self._text_ai_client.generate_text(
                prompt,
                temperature=0.4,
                max_tokens=900,
            )
            text = str(result.get("text") or "").strip()
        except Exception:
            return base_prompt
        return self._shorten(text, 2500) if text else base_prompt

    def _fallback_location_visual_prompt(self, location, project=None, world=None, owner=None) -> str:
        lines = [
            "Exterior key visual of a fictional world location, wide 1536x1024 landscape composition.",
            "Show the facility from outside: facade, entrance, surrounding streets or plaza, lighting, atmosphere, and landmark silhouette.",
            "Make it specific, story-rich, cinematic, and suitable for a location card thumbnail.",
            "Do not include readable text, captions, UI, logos, or watermarks.",
            f"Location name: {location.name or ''}",
            f"Location type: {location.location_type or ''}",
            f"Location description: {location.description or ''}",
            f"World/project: {getattr(project, 'title', '') or ''}",
            f"World tone: {getattr(world, 'tone', '') or ''}",
        ]
        if owner:
            lines.extend(
                [
                    "This location is associated with a character. Keep the facility as the main subject, and place the character naturally near the entrance or foreground.",
                    "Preserve character identity and style from the reference image if provided.",
                    f"Owner character: {owner.name or ''}",
                    f"Owner appearance: {owner.appearance_summary or ''}",
                    f"Owner art style: {owner.art_style or ''}",
                ]
            )
        return "\n".join(lines)

    def _build_map_image_prompt(self, project_id: int) -> str:
        project = self._project_service.get_project(project_id)
        world = self._world_service.get_world(project_id)
        locations = self._locations.list_by_project(project_id)
        lines = [
            "Create a 1536x1024 landscape overview image of a fictional world map / area map.",
            "The image should communicate the whole setting at a glance, like a beautiful game world map, city guide map, campus map, village map, or theme park guide depending on the world.",
            "This is not a precise GIS map. Do not draw coordinate grids. Make a readable atmospheric overview that helps users understand what kind of world this is.",
            "Show the relationships between major facilities with clear visual landmarks, roads, districts, paths, rivers, rails, plazas, or spatial groupings where appropriate.",
            "Do not include readable text, labels, letters, captions, UI, logos, or watermarks. Use icons, silhouettes, shapes, architecture, and landmarks instead of text labels.",
            "Use polished commercial key visual quality, strong composition, appealing colors, and enough detail to make the user want to explore.",
            f"World/project name: {getattr(project, 'title', '') or ''}",
            f"World/project summary: {getattr(project, 'summary', '') or ''}",
        ]
        if world:
            lines.extend(
                [
                    f"World tone: {world.tone or ''}",
                    f"Era: {world.era_description or ''}",
                    f"World overview: {world.overview or ''}",
                    f"Technology level: {world.technology_level or ''}",
                    f"Social structure: {world.social_structure or ''}",
                    f"Important facilities/rules: {world.rules_json or ''}",
                    f"Forbidden settings to avoid: {world.forbidden_json or ''}",
                ]
            )
        if locations:
            lines.append("Registered facilities to reflect as landmarks:")
            for location in locations[:40]:
                owner = self._characters.get(location.owner_character_id) if location.owner_character_id else None
                parts = [
                    f"name: {location.name or ''}",
                    f"region: {getattr(location, 'region', '') or ''}",
                    f"type: {location.location_type or ''}",
                    f"tags: {', '.join(self._tags_from_json(getattr(location, 'tags_json', None)))}",
                    f"description: {self._shorten(location.description, 260)}",
                ]
                if owner:
                    parts.append(f"owner: {owner.name or ''}")
                lines.append("- " + " / ".join(parts))
        else:
            lines.append("No registered facilities yet. Create a flexible overview with room for future landmarks.")
        return "\n".join(lines)

    def _store_generated_location_image(self, *, project_id: int, location_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except Exception as exc:
            raise RuntimeError("generated location image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT")
        directory = os.path.join(storage_root, "projects", str(project_id), "assets", "world_location_image")
        os.makedirs(directory, exist_ok=True)
        file_name = f"world_location_{location_id}_{uuid.uuid4().hex[:12]}.png"
        file_path = os.path.join(directory, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)

    def _store_generated_map_image(self, *, project_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except Exception as exc:
            raise RuntimeError("generated world map image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT")
        directory = os.path.join(storage_root, "projects", str(project_id), "assets", "world_map_image")
        os.makedirs(directory, exist_ok=True)
        file_name = f"world_map_{uuid.uuid4().hex[:12]}.png"
        file_path = os.path.join(directory, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)
