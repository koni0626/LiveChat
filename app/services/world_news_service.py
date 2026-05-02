from __future__ import annotations

import base64
import binascii
from datetime import datetime
import io
import os
import uuid

from flask import current_app
from PIL import Image

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..models import CinemaNovel, CinemaNovelChapter
from ..repositories.character_repository import CharacterRepository
from ..repositories.outing_session_repository import OutingSessionRepository
from ..repositories.world_location_repository import WorldLocationRepository
from ..repositories.world_news_repository import WorldNewsRepository
from ..utils import json_util
from .asset_service import AssetService
from .project_service import ProjectService
from .world_service import WorldService


class WorldNewsService:
    VALID_TYPES = {"location_news", "character_sighting", "relationship", "outing_afterglow", "event_hint", "cinema_novel"}

    def __init__(
        self,
        repository: WorldNewsRepository | None = None,
        character_repository: CharacterRepository | None = None,
        location_repository: WorldLocationRepository | None = None,
        outing_repository: OutingSessionRepository | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
        asset_service: AssetService | None = None,
    ):
        self._repo = repository or WorldNewsRepository()
        self._characters = character_repository or CharacterRepository()
        self._locations = location_repository or WorldLocationRepository()
        self._outings = outing_repository or OutingSessionRepository()
        self._projects = project_service or ProjectService()
        self._worlds = world_service or WorldService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._asset_service = asset_service or AssetService()

    def list_news(self, project_id: int, *, limit: int = 50) -> list[dict]:
        return [self.serialize_news(item) for item in self._repo.list_by_project(project_id, limit=limit)]

    def delete_news(self, project_id: int, news_id: int) -> bool:
        item = self._repo.get(news_id)
        if not item or item.project_id != project_id:
            return False
        return self._repo.delete(news_id)

    def create_manual(self, project_id: int, user_id: int, payload: dict) -> dict:
        normalized = self._normalize_payload(project_id, payload)
        normalized["created_by_user_id"] = user_id
        normalized.setdefault("source_type", "manual")
        row = self._repo.create(normalized)
        self._ensure_news_image(row)
        return self.serialize_news(row)

    def generate_manual(self, project_id: int, user_id: int, payload: dict | None = None) -> list[dict]:
        payload = dict(payload or {})
        count = max(1, min(5, int(payload.get("count") or 3)))
        candidates = self._generate_candidates(project_id, count=count)
        created = []
        for candidate in candidates[:count]:
            normalized = self._normalize_payload(
                project_id,
                {
                    **candidate,
                    "source_type": "manual_ai",
                    "created_by_user_id": user_id,
                    "return_url": candidate.get("return_url") or self._default_return_url(project_id, candidate),
                },
            )
            row = self._repo.create(normalized)
            self._ensure_news_image(row)
            created.append(self.serialize_news(row))
        return created

    def create_for_outing_completed(self, outing, character, location, state: dict | None = None) -> dict | None:
        existing = self._repo.find_by_source(
            project_id=outing.project_id,
            source_type="outing_completed",
            source_ref_type="outing",
            source_ref_id=outing.id,
        )
        if existing:
            if not existing.image_asset_id:
                self._ensure_news_image(existing)
            return self.serialize_news(existing)
        try:
            candidate = self._generate_outing_candidate(outing, character, location, state or {})
        except Exception:
            candidate = self._fallback_outing_candidate(outing, character, location)
        normalized = self._normalize_payload(
            outing.project_id,
            {
                **candidate,
                "created_by_user_id": outing.user_id,
                "related_character_id": character.id,
                "related_location_id": location.id,
                "news_type": candidate.get("news_type") or "outing_afterglow",
                "source_type": "outing_completed",
                "source_ref_type": "outing",
                "source_ref_id": outing.id,
                "return_url": f"/projects/{outing.project_id}/outings",
                "metadata_json": json_util.dumps(
                    {
                        "outing_id": outing.id,
                        "memory_title": outing.memory_title,
                        "memory_summary": outing.memory_summary,
                        "generated_at": datetime.utcnow().isoformat(),
                    }
                ),
            },
        )
        row = self._repo.create(normalized)
        self._ensure_news_image(row)
        return self.serialize_news(row)

    def serialize_news(self, item) -> dict | None:
        if not item:
            return None
        character = self._characters.get(item.related_character_id) if item.related_character_id else None
        location = self._locations.get(item.related_location_id) if item.related_location_id else None
        image_asset = self._asset_service.get_asset(item.image_asset_id) if item.image_asset_id else None
        return {
            "id": item.id,
            "project_id": item.project_id,
            "created_by_user_id": item.created_by_user_id,
            "related_character_id": item.related_character_id,
            "related_location_id": item.related_location_id,
            "related_character": self._serialize_character(character),
            "related_location": self._serialize_location(location),
            "news_type": item.news_type,
            "news_type_label": self._type_label(item.news_type),
            "title": item.title,
            "body": item.body,
            "summary": item.summary,
            "image_asset_id": item.image_asset_id,
            "image_asset": self._serialize_asset(image_asset),
            "importance": item.importance,
            "source_type": item.source_type,
            "source_ref_type": item.source_ref_type,
            "source_ref_id": item.source_ref_id,
            "return_url": item.return_url,
            "status": item.status,
            "metadata": self._load_json(item.metadata_json),
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    def _generate_candidates(self, project_id: int, *, count: int) -> list[dict]:
        project = self._projects.get_project(project_id)
        world = self._worlds.get_world(project_id)
        characters = self._characters.list_by_project(project_id)[:12]
        locations = self._locations.list_by_project(project_id)[:16]
        outings = self._outings.list_by_project_user(project_id, 1, limit=8)
        novels = self._recent_cinema_novel_contexts(project_id, limit=6)
        prompt = f"""
Return only JSON.
Create {count} world news / rumor items for a Japanese character world app.
They should make the world feel alive outside direct chat.

Required shape:
{{"items":[{{"news_type":"location_news|character_sighting|relationship|event_hint|cinema_novel","title":"...", "body":"...", "summary":"...", "importance":1-5, "related_character_id": null or number, "related_location_id": null or number, "source_ref_type": null or "cinema_novel", "source_ref_id": null or number}}]}}

Rules:
- Japanese only.
- Keep each body 100-220 chars.
- Include a mix of facility news, character sightings, character relationship rumors, and novel-related rumors if cinema novels are provided.
- Do not claim huge irreversible events. Make them small hooks for chat or outing.
- Use only provided character/location IDs.
- If using a cinema novel as inspiration, make it sound like an in-world screening rumor, production note, audience reaction, character sighting around the theater, or a small story-world echo. Do not summarize the whole novel.
- For novel-related items, set news_type to "cinema_novel", source_ref_type to "cinema_novel", and source_ref_id to the provided novel id.

Project: {getattr(project, "title", "") or ""}
Project summary: {getattr(project, "summary", "") or ""}
World tone: {getattr(world, "tone", "") if world else ""}
World overview: {getattr(world, "overview", "") if world else ""}
Characters: {json_util.dumps([self._character_context(c) for c in characters])}
Locations: {json_util.dumps([self._location_context(l) for l in locations])}
Recent outings: {json_util.dumps([{"id": o.id, "title": o.title, "summary": o.memory_summary or o.summary} for o in outings])}
Cinema novels: {json_util.dumps(novels)}
""".strip()
        result = self._text_ai_client.generate_text(
            prompt,
            response_format={"type": "json_object"},
            temperature=0.85,
            max_tokens=1600,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        items = parsed.get("items") if isinstance(parsed, dict) else []
        if isinstance(items, list) and items:
            return [item for item in items if isinstance(item, dict)]
        return self._fallback_candidates(project_id, count)

    def _generate_outing_candidate(self, outing, character, location, state: dict) -> dict:
        prompt = f"""
Return only JSON.
Create one small world news / rumor item that appears after an outing mini event.
It should sound like a city rumor, sighting, or local note, not a private diary.

Required keys:
{{"news_type":"outing_afterglow|character_sighting|relationship", "title":"...", "body":"...", "summary":"...", "importance":1-5}}

Character: {character.name or ""}
Character overview: {getattr(character, "character_summary", None) or ""}
Character personality: {character.personality or ""}
Location: {location.name or ""}
Location description: {location.description or ""}
Outing title: {outing.title or ""}
Mood: {outing.mood or ""}
Memory title: {outing.memory_title or ""}
Memory summary: {outing.memory_summary or ""}
Selected choices: {json_util.dumps((state or {}).get("selected_choices") or [])}
""".strip()
        result = self._text_ai_client.generate_text(
            prompt,
            response_format={"type": "json_object"},
            temperature=0.75,
            max_tokens=700,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        return parsed if isinstance(parsed, dict) else self._fallback_outing_candidate(outing, character, location)

    def _fallback_candidates(self, project_id: int, count: int) -> list[dict]:
        locations = self._locations.list_by_project(project_id)
        characters = self._characters.list_by_project(project_id)
        items = []
        for index in range(count):
            location = locations[index % len(locations)] if locations else None
            character = characters[index % len(characters)] if characters else None
            items.append(
                {
                    "news_type": "character_sighting" if character else "location_news",
                    "title": f"{getattr(location, 'name', None) or '街角'}で小さな噂",
                    "body": f"{getattr(character, 'name', '誰か')}が{getattr(location, 'name', '街のどこか')}の近くにいた、という話が少しだけ広がっている。何か大きな事件ではないが、次に会ったとき話題にできそうな空気がある。",
                    "summary": "街で小さな噂が流れている。",
                    "importance": 3,
                    "related_character_id": getattr(character, "id", None),
                    "related_location_id": getattr(location, "id", None),
                }
            )
        return items

    def _fallback_outing_candidate(self, outing, character, location) -> dict:
        return {
            "news_type": "outing_afterglow",
            "title": f"{location.name}で見かけた二人",
            "body": f"{location.name}で、{character.name}が誰かと楽しそうに過ごしていたという噂が流れている。大きな出来事ではないが、その場にいた人には少し印象に残る時間だったらしい。",
            "summary": f"{location.name}で{character.name}の目撃情報があった。",
            "importance": 3,
        }

    def _normalize_payload(self, project_id: int, payload: dict) -> dict:
        title = str(payload.get("title") or "").strip()
        body = str(payload.get("body") or "").strip()
        if not title:
            title = "街の噂"
        if not body:
            body = "街のどこかで、小さな噂が流れている。"
        news_type = str(payload.get("news_type") or "location_news").strip()
        if news_type not in self.VALID_TYPES:
            news_type = "location_news"
        return {
            "project_id": project_id,
            "created_by_user_id": payload.get("created_by_user_id"),
            "related_character_id": self._valid_character_id(project_id, payload.get("related_character_id")),
            "related_location_id": self._valid_location_id(project_id, payload.get("related_location_id")),
            "news_type": news_type,
            "title": title[:255],
            "body": body,
            "summary": str(payload.get("summary") or "").strip()[:500] or None,
            "importance": max(1, min(5, int(payload.get("importance") or 3))),
            "source_type": str(payload.get("source_type") or "manual_ai").strip()[:80],
            "source_ref_type": str(payload.get("source_ref_type") or "").strip()[:80] or None,
            "source_ref_id": payload.get("source_ref_id"),
            "return_url": str(payload.get("return_url") or "").strip()[:512] or self._default_return_url(project_id, payload),
            "status": str(payload.get("status") or "published").strip()[:50],
            "metadata_json": payload.get("metadata_json"),
        }

    def _ensure_news_image(self, item):
        if not item or item.image_asset_id:
            return item
        generated_at = datetime.utcnow().isoformat()
        try:
            asset, generation_meta = self._generate_news_image(item)
        except Exception as exc:
            current_app.logger.warning(
                "world news image generation failed for news_id=%s: %s",
                getattr(item, "id", None),
                exc,
            )
            self._record_news_image_generation_state(
                item,
                {
                    "status": "error",
                    "error": str(exc)[:500],
                    "generated_at": generated_at,
                },
            )
            return item
        if not asset:
            generation_meta = dict(generation_meta or {})
            generation_meta.setdefault("status", "empty_response")
            generation_meta.setdefault("generated_at", generated_at)
            self._record_news_image_generation_state(item, generation_meta)
            return item
        item.image_asset_id = asset.id
        metadata = self._load_json(item.metadata_json)
        metadata["news_image_asset_id"] = asset.id
        metadata["news_image_generated_at"] = generated_at
        metadata["news_image_generation"] = {
            **(generation_meta or {}),
            "status": "success",
            "asset_id": asset.id,
            "generated_at": generated_at,
        }
        item.metadata_json = json_util.dumps(metadata)
        from ..extensions import db

        db.session.commit()
        return item

    def _record_news_image_generation_state(self, item, generation_state: dict):
        metadata = self._load_json(getattr(item, "metadata_json", None))
        attempts = metadata.get("news_image_generation_attempts")
        if not isinstance(attempts, list):
            attempts = []
        state = dict(generation_state or {})
        state.setdefault("generated_at", datetime.utcnow().isoformat())
        attempts.append(state)
        metadata["news_image_generation"] = state
        metadata["news_image_generation_attempts"] = attempts[-8:]
        item.metadata_json = json_util.dumps(metadata)
        from ..extensions import db

        db.session.commit()
        return item

    def _generate_news_image(self, item):
        character = self._characters.get(item.related_character_id) if item.related_character_id else None
        location = self._locations.get(item.related_location_id) if item.related_location_id else None
        project = self._projects.get_project(item.project_id)
        reference_characters = self._news_image_reference_characters(item.project_id, item, character)
        reference_paths, reference_asset_ids, referenced_characters = self._news_image_references(
            item.project_id, reference_characters
        )
        prompt = self._build_news_image_prompt(item, character, location, project, referenced_characters)
        result = self._image_ai_client.generate_image(
            prompt,
            size="1536x1024",
            quality=current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            output_format="png",
            background="opaque",
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        generation_meta = {
            "provider": result.get("provider"),
            "model": result.get("model"),
            "quality": result.get("quality"),
            "size": "1536x1024",
            "aspect_ratio": result.get("aspect_ratio"),
            "operation": result.get("operation"),
            "reference_asset_ids": reference_asset_ids,
            "reference_character_ids": [character.id for character in referenced_characters],
            "reference_image_count": result.get("reference_image_count"),
            "input_fidelity": result.get("input_fidelity"),
            "output_format": result.get("output_format"),
            "safety_preflight": result.get("safety_preflight"),
            "safety_retry": result.get("safety_retry"),
            "revised_prompt": result.get("revised_prompt"),
        }
        image_base64 = result.get("image_base64")
        if not image_base64:
            generation_meta["raw_response_keys"] = sorted(list((result.get("raw_response") or {}).keys()))
            return None, generation_meta
        file_name, file_path, file_size, width, height = self._store_news_image(item.project_id, item.id, image_base64)
        asset = self._asset_service.create_asset(
            item.project_id,
            {
                "asset_type": "world_news_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "width": width,
                "height": height,
                "metadata_json": json_util.dumps(
                    {
                        "source": "world_news_image",
                        "news_id": item.id,
                        "provider": result.get("provider"),
                        "model": result.get("model"),
                        "quality": result.get("quality"),
                        "size": "1536x1024",
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_asset_ids,
                        "reference_character_ids": [character.id for character in referenced_characters],
                        "reference_image_count": result.get("reference_image_count"),
                        "input_fidelity": result.get("input_fidelity"),
                    }
                ),
            },
        )
        return asset, generation_meta

    def _news_image_reference_characters(self, project_id: int, item, primary_character) -> list:
        candidates = self._characters.list_by_project(project_id)
        text = "\n".join(
            [
                str(getattr(item, "title", "") or ""),
                str(getattr(item, "body", "") or ""),
                str(getattr(item, "summary", "") or ""),
            ]
        )
        selected = []
        seen_ids = set()
        if primary_character:
            selected.append(primary_character)
            seen_ids.add(primary_character.id)
        matches = []
        for character in candidates:
            if character.id in seen_ids:
                continue
            names = [
                str(getattr(character, "name", "") or "").strip(),
                str(getattr(character, "nickname", "") or "").strip(),
            ]
            positions = [text.find(name) for name in names if len(name) >= 2 and name in text]
            positions = [position for position in positions if position >= 0]
            if positions:
                matches.append((min(positions), character.id, character))
        for _position, _character_id, matched_character in sorted(matches):
            selected.append(matched_character)
            if len(selected) >= 2:
                break
        return selected

    def _news_image_references(self, project_id: int, characters: list) -> tuple[list[str], list[int], list]:
        paths = []
        asset_ids = []
        referenced_characters = []
        seen_asset_ids = set()
        for character in characters[:2]:
            if not character or not getattr(character, "base_asset_id", None):
                continue
            asset = self._asset_service.get_asset(character.base_asset_id)
            if not asset or asset.project_id != project_id or not asset.file_path:
                continue
            if asset.id in seen_asset_ids or not os.path.exists(asset.file_path):
                continue
            paths.append(asset.file_path)
            asset_ids.append(asset.id)
            referenced_characters.append(character)
            seen_asset_ids.add(asset.id)
        return paths, asset_ids, referenced_characters

    def _build_news_image_prompt(self, item, character, location, project, reference_characters: list | None = None) -> str:
        reference_characters = reference_characters or []
        lines = [
            "Create a polished in-world news image for a Japanese character/world app.",
            "It should look like a modern local news card, not a plain illustration.",
            "Landscape 1536x1024, cinematic news photography with a clear news graphic layout.",
            "Use realistic editorial photography, documentary/event-news lighting, natural camera perspective, and believable environment detail.",
            "Avoid anime illustration, painterly rendering, visual novel CG style, cel shading, manga line art, or stylized character poster framing.",
            "Include a fictional news logo in the upper left: LAPLACE NEWS.",
            "Include broadcast-style elements: top logo bar, lower-third headline strip, small category badge, subtle ticker-like decorative line.",
            "Use large, readable Japanese headline text based on the title. Keep text short; avoid long paragraphs.",
            "Do not use real broadcaster logos, real newspaper brands, watermarks, QR codes, or UI screenshots.",
            "The image should still show the reported scene: city, facility, character sighting, local event, or rumor atmosphere.",
            "Avoid making it look like a character standing portrait only.",
        ]
        if reference_characters:
            lines.extend(
                [
                    f"{len(reference_characters)} base character reference image(s) are provided.",
                    "Use each provided base character image as a separate identity reference.",
                    "Preserve each referenced character's face identity, hairstyle, hair color, eye shape, body impression, and overall character design.",
                    "If two referenced characters are present in the news title/body, show both of them and do not invent a different second person.",
                    "Use the references for identity, not as a reason to make the whole image illustrated; if a reference is illustrated, translate that identity into a realistic news-photo look.",
                    "Do not use thumbnails, icons, avatars, or cropped portraits as identity references.",
                    "Adapt the character(s) into the news scene while preserving identity from the base image(s).",
                ]
            )
            for index, referenced_character in enumerate(reference_characters, start=1):
                lines.append(
                    f"Reference character {index}: {referenced_character.name or ''} / nickname: {referenced_character.nickname or ''} / appearance: {referenced_character.appearance_summary or ''}"
                )
        lines.extend(
            [
                f"Project/world name: {getattr(project, 'title', '') or ''}",
                f"News type: {item.news_type}",
                f"News title/headline: {item.title}",
                f"News body/context: {item.body}",
                f"Related character: {getattr(character, 'name', '') if character else ''}",
                f"Character appearance/personality: {getattr(character, 'appearance_summary', '') if character else ''} / {getattr(character, 'personality', '') if character else ''}",
                f"Related location: {getattr(location, 'name', '') if location else ''}",
                f"Location description: {getattr(location, 'description', '') if location else ''}",
            ]
        )
        return "\n".join(lines)

    def _store_news_image(self, project_id: int, news_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated news image payload is invalid") from exc
        with Image.open(io.BytesIO(raw_bytes)) as image:
            width, height = image.size
        directory = os.path.join(
            current_app.config.get("STORAGE_ROOT"),
            "projects",
            str(project_id),
            "generated",
            "world_news",
            str(news_id),
        )
        os.makedirs(directory, exist_ok=True)
        file_name = f"world_news_{news_id}_{uuid.uuid4().hex[:12]}.png"
        file_path = os.path.join(directory, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes), width, height

    def _default_return_url(self, project_id: int, payload: dict) -> str:
        if payload.get("source_ref_type") == "cinema_novel" and payload.get("source_ref_id"):
            return f"/projects/{project_id}/cinema-novels"
        location_id = payload.get("related_location_id")
        if location_id:
            return f"/projects/{project_id}/outings"
        return f"/projects/{project_id}/world-news"

    def _valid_character_id(self, project_id: int, value):
        try:
            character_id = int(value or 0)
        except (TypeError, ValueError):
            return None
        character = self._characters.get(character_id)
        return character.id if character and character.project_id == project_id else None

    def _valid_location_id(self, project_id: int, value):
        try:
            location_id = int(value or 0)
        except (TypeError, ValueError):
            return None
        location = self._locations.get(location_id)
        return location.id if location and location.project_id == project_id else None

    def _character_context(self, character) -> dict:
        return {
            "id": character.id,
            "name": character.name,
            "character_summary": getattr(character, "character_summary", None),
            "personality": character.personality,
        }

    def _location_context(self, location) -> dict:
        return {"id": location.id, "name": location.name, "type": location.location_type, "description": location.description}

    def _recent_cinema_novel_contexts(self, project_id: int, *, limit: int = 6) -> list[dict]:
        novels = (
            CinemaNovel.query.filter(
                CinemaNovel.project_id == project_id,
                CinemaNovel.deleted_at.is_(None),
            )
            .order_by(CinemaNovel.updated_at.desc(), CinemaNovel.id.desc())
            .limit(limit)
            .all()
        )
        contexts = []
        for novel in novels:
            production = self._load_json(getattr(novel, "production_json", None))
            source_input = production.get("source_input") if isinstance(production.get("source_input"), dict) else {}
            chapters = (
                CinemaNovelChapter.query.filter(
                    CinemaNovelChapter.novel_id == novel.id,
                    CinemaNovelChapter.deleted_at.is_(None),
                )
                .order_by(CinemaNovelChapter.chapter_no.asc(), CinemaNovelChapter.sort_order.asc(), CinemaNovelChapter.id.asc())
                .limit(8)
                .all()
            )
            contexts.append(
                {
                    "id": novel.id,
                    "title": novel.title,
                    "subtitle": novel.subtitle,
                    "description": self._shorten(getattr(novel, "description", None), 600),
                    "status": novel.status,
                    "main_character": source_input.get("main_character") or "",
                    "genre": source_input.get("genre") or "",
                    "theme": source_input.get("theme") or "",
                    "concept_note": self._shorten(source_input.get("concept_note"), 500),
                    "outline": self._shorten(production.get("outline_markdown"), 1200),
                    "chapters": [
                        {
                            "chapter_no": chapter.chapter_no,
                            "title": chapter.title,
                            "excerpt": self._shorten(chapter.body_markdown, 350),
                        }
                        for chapter in chapters
                    ],
                }
            )
        return contexts

    def _shorten(self, value, limit: int) -> str:
        text = str(value or "").strip().replace("\r\n", "\n")
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def _serialize_character(self, character) -> dict | None:
        if not character:
            return None
        return {"id": character.id, "name": character.name, "nickname": character.nickname}

    def _serialize_location(self, location) -> dict | None:
        if not location:
            return None
        return {"id": location.id, "name": location.name, "region": location.region, "location_type": location.location_type}

    def _serialize_asset(self, asset) -> dict | None:
        if not asset:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "mime_type": asset.mime_type,
            "width": asset.width,
            "height": asset.height,
            "media_url": self._media_url(asset.file_path),
        }

    def _media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        if not storage_root:
            return None
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        try:
            if os.path.commonpath([normalized_path, normalized_root]) != normalized_root:
                return None
        except ValueError:
            return None
        return f"/media/{os.path.relpath(normalized_path, normalized_root).replace(os.sep, '/')}"

    def _type_label(self, news_type: str) -> str:
        return {
            "location_news": "施設ニュース",
            "character_sighting": "目撃情報",
            "relationship": "関係の噂",
            "outing_afterglow": "おでかけ後日談",
            "event_hint": "イベント予告",
            "cinema_novel": "ノベル",
        }.get(news_type, "噂")

    def _load_json(self, value) -> dict:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json_util.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
