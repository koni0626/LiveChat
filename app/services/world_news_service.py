from __future__ import annotations

from datetime import datetime

from ..clients.text_ai_client import TextAIClient
from ..repositories.character_repository import CharacterRepository
from ..repositories.outing_session_repository import OutingSessionRepository
from ..repositories.world_location_repository import WorldLocationRepository
from ..repositories.world_news_repository import WorldNewsRepository
from ..utils import json_util
from .project_service import ProjectService
from .world_service import WorldService


class WorldNewsService:
    VALID_TYPES = {"location_news", "character_sighting", "relationship", "outing_afterglow", "event_hint"}

    def __init__(
        self,
        repository: WorldNewsRepository | None = None,
        character_repository: CharacterRepository | None = None,
        location_repository: WorldLocationRepository | None = None,
        outing_repository: OutingSessionRepository | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        text_ai_client: TextAIClient | None = None,
    ):
        self._repo = repository or WorldNewsRepository()
        self._characters = character_repository or CharacterRepository()
        self._locations = location_repository or WorldLocationRepository()
        self._outings = outing_repository or OutingSessionRepository()
        self._projects = project_service or ProjectService()
        self._worlds = world_service or WorldService()
        self._text_ai_client = text_ai_client or TextAIClient()

    def list_news(self, project_id: int, *, limit: int = 50) -> list[dict]:
        return [self.serialize_news(item) for item in self._repo.list_by_project(project_id, limit=limit)]

    def create_manual(self, project_id: int, user_id: int, payload: dict) -> dict:
        normalized = self._normalize_payload(project_id, payload)
        normalized["created_by_user_id"] = user_id
        normalized.setdefault("source_type", "manual")
        return self.serialize_news(self._repo.create(normalized))

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
            created.append(self.serialize_news(self._repo.create(normalized)))
        return created

    def create_for_outing_completed(self, outing, character, location, state: dict | None = None) -> dict | None:
        existing = self._repo.find_by_source(
            project_id=outing.project_id,
            source_type="outing_completed",
            source_ref_type="outing",
            source_ref_id=outing.id,
        )
        if existing:
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
        return self.serialize_news(self._repo.create(normalized))

    def serialize_news(self, item) -> dict | None:
        if not item:
            return None
        character = self._characters.get(item.related_character_id) if item.related_character_id else None
        location = self._locations.get(item.related_location_id) if item.related_location_id else None
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
        prompt = f"""
Return only JSON.
Create {count} world news / rumor items for a Japanese character world app.
They should make the world feel alive outside direct chat.

Required shape:
{{"items":[{{"news_type":"location_news|character_sighting|relationship|event_hint","title":"...", "body":"...", "summary":"...", "importance":1-5, "related_character_id": null or number, "related_location_id": null or number}}]}}

Rules:
- Japanese only.
- Keep each body 100-220 chars.
- Include a mix of facility news, character sightings, and character relationship rumors.
- Do not claim huge irreversible events. Make them small hooks for chat or outing.
- Use only provided character/location IDs.

Project: {getattr(project, "title", "") or ""}
Project summary: {getattr(project, "summary", "") or ""}
World tone: {getattr(world, "tone", "") if world else ""}
World overview: {getattr(world, "overview", "") if world else ""}
Characters: {json_util.dumps([self._character_context(c) for c in characters])}
Locations: {json_util.dumps([self._location_context(l) for l in locations])}
Recent outings: {json_util.dumps([{"id": o.id, "title": o.title, "summary": o.memory_summary or o.summary} for o in outings])}
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

    def _default_return_url(self, project_id: int, payload: dict) -> str:
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
        return {"id": character.id, "name": character.name, "personality": character.personality}

    def _location_context(self, location) -> dict:
        return {"id": location.id, "name": location.name, "type": location.location_type, "description": location.description}

    def _serialize_character(self, character) -> dict | None:
        if not character:
            return None
        return {"id": character.id, "name": character.name, "nickname": character.nickname}

    def _serialize_location(self, location) -> dict | None:
        if not location:
            return None
        return {"id": location.id, "name": location.name, "region": location.region, "location_type": location.location_type}

    def _type_label(self, news_type: str) -> str:
        return {
            "location_news": "施設ニュース",
            "character_sighting": "目撃情報",
            "relationship": "関係の噂",
            "outing_afterglow": "おでかけ後日談",
            "event_hint": "イベント予告",
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
