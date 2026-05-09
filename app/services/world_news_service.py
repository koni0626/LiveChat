from __future__ import annotations

import base64
import binascii
from datetime import datetime
import io
import os
import random
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
        count = max(1, min(5, int(payload.get("count") or 1)))
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
        characters = self._characters.list_by_project(project_id)
        locations = self._locations.list_by_project(project_id)
        outings = self._outings.list_by_project_user(project_id, 1, limit=8)
        novels = self._recent_cinema_novel_contexts(project_id, limit=6)
        plans = self._build_news_generation_plans(
            project_id,
            count=count,
            characters=characters,
            locations=locations,
            outings=outings,
            novels=novels,
        )
        prompt = f"""
JSONのみを返してください。
日本語キャラクター世界観アプリ向けに、世界ニュース/噂を {count} 件作成してください。
直接チャットしていない場所でも世界が生きているように感じさせてください。

必須形式:
{{"items":[{{"plan_id":1,"news_type":"location_news|character_sighting|relationship|event_hint|outing_afterglow|cinema_novel","title":"...", "body":"...", "summary":"...", "importance":1-5, "related_character_id": null or number, "related_location_id": null or number, "source_ref_type": null or "cinema_novel" or "outing", "source_ref_id": null or number}}]}}

ルール:
- 日本語のみ。
- 各 body は100〜220文字。
- 施設ニュース、キャラクター目撃談、キャラクター関係の噂、シネマノベルが提供されている場合はノベル関連の噂を混ぜてください。
- 大規模で不可逆な事件を断定しないでください。チャットやおでかけの小さなフックにしてください。
- 提供されたキャラクターID/場所IDだけを使ってください。
- シネマノベルを着想に使う場合は、世界内の上映噂、制作メモ、観客反応、劇場周辺のキャラクター目撃、小さな物語世界の反響のようにしてください。ノベル全体の要約はしないでください。
- ノベル関連項目では、news_type を "cinema_novel"、source_ref_type を "cinema_novel"、source_ref_id を提供されたノベルIDにしてください。

Romcom gossip intensity:
- Treat each item as an in-world local scoop with stronger love-comedy flavor than ordinary news.
- Prefer blushes, awkward distance, accidental eye contact, almost-confessions, jealous reactions, overread gestures, misunderstood date-like situations, and bystanders overreacting.
- Make the reported evidence concrete: who noticed what, where it happened, what object/line/reaction caused the rumor, and why the crowd is amused.
- Keep it playful and non-explicit. Turn suggestive or sensitive material into safe romantic tension, boundaries, fashion mishaps, public reactions, or awkward timing.
- Do not make it a private diary. It should read like a short rumor/news report that the world could plausibly circulate.
Randomized plan contract:
- Create exactly one item for each news_plan.
- Do not choose the article type, main character, location, or source yourself. They were already selected randomly by the system.
- Keep plan_id, news_type, related_character_id, related_location_id, source_ref_type, and source_ref_id exactly as specified in each plan. If a plan field is null, keep it null.
- Use the plan's article_tone, comedy_style, romcom_intensity, beat, object_hook, and public_reaction as the article seed.
- Vary the writing texture according to article_tone. Some plans should read like a serious report on a silly incident, some like gossip, some like a dry city notice, some like a tabloid scoop, and some like a warm afterglow.
- romcom_intensity controls how visible the romantic tension should be: low is a small hint, medium is readable tension, high is obvious love-comedy energy.
- If source_kind is outing, use the outing memory as the seed. If source_kind is cinema_novel, use it as a local screening/production/audience rumor, not a full plot summary.
プロジェクト: {getattr(project, "title", "") or ""}
プロジェクト概要: {getattr(project, "summary", "") or ""}
世界観トーン: {getattr(world, "tone", "") if world else ""}
世界観概要: {getattr(world, "overview", "") if world else ""}
news_plans: {json_util.dumps(plans)}
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
            return self._apply_news_plans(items, plans)
        return self._fallback_candidates(project_id, count, plans=plans)

    def _build_news_generation_plans(
        self,
        project_id: int,
        *,
        count: int,
        characters: list,
        locations: list,
        outings: list,
        novels: list[dict],
    ) -> list[dict]:
        recent_items = self._repo.list_by_project(project_id, limit=40) if hasattr(self._repo, "list_by_project") else []
        recent_location_counts: dict[int, int] = {}
        recent_character_counts: dict[int, int] = {}
        for item in recent_items:
            if getattr(item, "related_location_id", None):
                recent_location_counts[int(item.related_location_id)] = recent_location_counts.get(int(item.related_location_id), 0) + 1
            if getattr(item, "related_character_id", None):
                recent_character_counts[int(item.related_character_id)] = recent_character_counts.get(int(item.related_character_id), 0) + 1

        news_types = ["location_news", "character_sighting", "relationship", "event_hint"]
        if outings:
            news_types.append("outing_afterglow")
        if novels:
            news_types.append("cinema_novel")

        used_location_ids: set[int] = set()
        used_character_ids: set[int] = set()
        plans = []
        for index in range(max(1, int(count or 1))):
            news_type = random.choice(news_types)
            article_tone = random.choice(
                [
                    "serious_report_on_silly_incident",
                    "romcom_gossip",
                    "deadpan_city_notice",
                    "tabloid_scoop",
                    "heartwarming_afterglow",
                    "ominous_but_small",
                    "chaotic_bystander_report",
                ]
            )
            comedy_style = random.choice(
                [
                    "deadpan",
                    "overdramatic",
                    "misunderstanding",
                    "witness_quotes",
                    "bureaucratic_absurdity",
                    "reaction_comedy",
                    "quiet_embarrassment",
                ]
            )
            romcom_intensity = random.choice(["low", "medium", "high", "high"])
            character = self._weighted_choice(characters, recent_character_counts, used_character_ids)
            location = self._weighted_choice(locations, recent_location_counts, used_location_ids)
            source_kind = "random"
            source_ref_type = None
            source_ref_id = None
            source_context = None

            if news_type == "cinema_novel" and novels:
                novel = random.choice(novels)
                source_kind = "cinema_novel"
                source_ref_type = "cinema_novel"
                source_ref_id = novel.get("id")
                source_context = {
                    "title": novel.get("title"),
                    "subtitle": novel.get("subtitle"),
                    "genre": novel.get("genre"),
                    "theme": novel.get("theme"),
                    "description": novel.get("description"),
                }
            elif news_type == "outing_afterglow" and outings:
                outing = random.choice(outings)
                source_kind = "outing"
                source_ref_type = "outing"
                source_ref_id = getattr(outing, "id", None)
                source_context = {
                    "title": getattr(outing, "title", None),
                    "mood": getattr(outing, "mood", None),
                    "memory_title": getattr(outing, "memory_title", None),
                    "memory_summary": getattr(outing, "memory_summary", None) or getattr(outing, "summary", None),
                }
                if getattr(outing, "location_id", None):
                    location = self._location_by_id(locations, outing.location_id) or location

            if news_type == "location_news":
                character = character if random.random() < 0.65 else None
            elif news_type in {"character_sighting", "relationship"} and not character:
                character = self._weighted_choice(characters, recent_character_counts, used_character_ids)
            elif news_type == "event_hint" and random.random() < 0.3:
                character = None

            co_character = None
            if news_type == "relationship" and character:
                co_candidates = [candidate for candidate in characters if getattr(candidate, "id", None) != getattr(character, "id", None)]
                co_character = random.choice(co_candidates) if co_candidates else None

            if character and getattr(character, "id", None):
                used_character_ids.add(int(character.id))
            if location and getattr(location, "id", None):
                used_location_ids.add(int(location.id))

            plans.append(
                {
                    "plan_id": index + 1,
                    "news_type": news_type,
                    "related_character_id": getattr(character, "id", None),
                    "related_character": self._character_context(character) if character else None,
                    "co_character_id": getattr(co_character, "id", None),
                    "co_character": self._character_context(co_character) if co_character else None,
                    "related_location_id": getattr(location, "id", None),
                    "related_location": self._location_context(location) if location else None,
                    "source_kind": source_kind,
                    "source_ref_type": source_ref_type,
                    "source_ref_id": source_ref_id,
                    "source_context": source_context,
                    "article_tone": article_tone,
                    "article_tone_instruction": self._article_tone_instruction(article_tone),
                    "comedy_style": comedy_style,
                    "comedy_style_instruction": self._comedy_style_instruction(comedy_style),
                    "romcom_intensity": romcom_intensity,
                    "romcom_intensity_instruction": self._romcom_intensity_instruction(romcom_intensity),
                    "beat": random.choice(
                        [
                            "accidental eye contact becomes a public rumor",
                            "someone denies caring too fast",
                            "a small object makes the misunderstanding obvious",
                            "bystanders overreact to a harmless moment",
                            "a jealous reaction is noticed before it is hidden",
                            "an almost-confession is interrupted by bad timing",
                            "a practical favor looks like a date",
                            "a failed attempt to act normal becomes the headline",
                        ]
                    ),
                    "object_hook": random.choice(
                        [
                            "receipt",
                            "reserved seat sign",
                            "shared menu",
                            "forgotten accessory",
                            "photo booth print",
                            "notification sound",
                            "half-finished drink",
                            "handwritten note",
                            "umbrella",
                            "staff comment",
                        ]
                    ),
                    "public_reaction": random.choice(
                        [
                            "witnesses quietly started guessing the relationship",
                            "staff pretended not to notice but failed",
                            "nearby customers treated it like breaking news",
                            "someone posted a teasing one-line rumor",
                            "the crowd noticed the silence after the denial",
                            "the official explanation only made it sound more suspicious",
                        ]
                    ),
                }
            )
        return plans

    def _article_tone_instruction(self, tone: str) -> str:
        return {
            "serious_report_on_silly_incident": "Report a ridiculous or tiny incident with a straight face, as if it deserves formal local coverage.",
            "romcom_gossip": "Lean into relationship rumors, teasing witnesses, and visible romantic tension.",
            "deadpan_city_notice": "Write like a dry municipal notice where the absurdity comes from the calm official wording.",
            "tabloid_scoop": "Make it feel like an exaggerated but harmless scoop with a catchy headline.",
            "heartwarming_afterglow": "Make the story gently warm, with a small emotional afterglow and a soft punchline.",
            "ominous_but_small": "Add a faintly ominous city-rumor mood, but keep the actual event small and safe.",
            "chaotic_bystander_report": "Center the confused, excited, or conflicting reactions of bystanders.",
        }.get(tone, "Write a concise local rumor/news item with a clear angle.")

    def _comedy_style_instruction(self, style: str) -> str:
        return {
            "deadpan": "Keep the wording calm and let the gap between tone and event create the joke.",
            "overdramatic": "Use a slightly dramatic news angle for a very small event.",
            "misunderstanding": "Build the joke around a harmless misunderstanding that looks romantic or suspicious.",
            "witness_quotes": "Use reported witness reactions or short paraphrased comments as the comedic engine.",
            "bureaucratic_absurdity": "Make official rules, notices, rankings, or procedures sound absurdly serious.",
            "reaction_comedy": "Focus on facial reactions, silence, denials, and the crowd noticing them.",
            "quiet_embarrassment": "Keep the comedy small, awkward, and carried by embarrassment rather than loud jokes.",
        }.get(style, "Use a light comedic angle.")

    def _romcom_intensity_instruction(self, intensity: str) -> str:
        return {
            "low": "Use only a faint romantic hint; the article can still be mostly about the local incident.",
            "medium": "Make the romantic tension readable but not overwhelming.",
            "high": "Make the love-comedy energy obvious through blushes, denial, jealousy, distance, or witness teasing.",
        }.get(intensity, "Make the romantic tension readable but safe.")

    def _apply_news_plans(self, items: list, plans: list[dict]) -> list[dict]:
        plan_by_id = {int(plan.get("plan_id")): plan for plan in plans if plan.get("plan_id")}
        applied = []
        for index, raw_item in enumerate(items[: len(plans)]):
            if not isinstance(raw_item, dict):
                continue
            try:
                plan_id = int(raw_item.get("plan_id") or index + 1)
            except (TypeError, ValueError):
                plan_id = index + 1
            plan = plan_by_id.get(plan_id) or (plans[index] if index < len(plans) else {})
            applied.append(self._merge_item_with_plan(raw_item, plan))
        while len(applied) < len(plans):
            applied.append(self._fallback_item_from_plan(plans[len(applied)]))
        return applied

    def _merge_item_with_plan(self, item: dict, plan: dict) -> dict:
        merged = dict(item or {})
        merged["news_type"] = plan.get("news_type") or merged.get("news_type")
        merged["related_character_id"] = plan.get("related_character_id")
        merged["related_location_id"] = plan.get("related_location_id")
        merged["source_ref_type"] = plan.get("source_ref_type")
        merged["source_ref_id"] = plan.get("source_ref_id")
        metadata = self._load_json(merged.get("metadata_json"))
        metadata["generation_plan"] = plan
        merged["metadata_json"] = json_util.dumps(metadata)
        return merged

    def _fallback_item_from_plan(self, plan: dict) -> dict:
        location = ((plan or {}).get("related_location") or {}).get("name") or "街のどこか"
        character = ((plan or {}).get("related_character") or {}).get("name") or "誰か"
        beat = (plan or {}).get("beat") or "小さな噂"
        object_hook = (plan or {}).get("object_hook") or "小物"
        article_tone = (plan or {}).get("article_tone") or "romcom_gossip"
        if article_tone == "deadpan_city_notice":
            body = f"{location}では、{character}に関する{object_hook}の取り扱いについて小規模な注目が集まっている。関係者は平静を保っているが、目撃者の間では{beat}として記録されつつある。"
        elif article_tone == "serious_report_on_silly_incident":
            body = f"{location}で{character}をめぐる些細な出来事が、なぜか真剣に受け止められている。発端は{object_hook}で、現場では{beat}として周囲が静かにざわついたという。"
        elif article_tone == "tabloid_scoop":
            body = f"{location}で{character}に関する新たな目撃談が浮上した。鍵を握るのは{object_hook}。現場では{beat}として扱われ、周囲の反応まで妙に熱を帯びている。"
        else:
            body = f"{location}で{character}に関する小さな噂が流れている。きっかけは{object_hook}と、目撃者が気づいた妙な間だったらしい。大事件ではないが、{beat}として周囲が少し盛り上がっている。"
        return self._merge_item_with_plan(
            {
                "title": f"{location}で小さな噂",
                "body": body,
                "summary": body[:120],
                "importance": 3,
            },
            plan,
        )

    def _weighted_choice(self, values: list, recent_counts: dict[int, int], used_ids: set[int]):
        available = [value for value in values if getattr(value, "id", None)]
        if not available:
            return None
        weights = []
        for value in available:
            value_id = int(value.id)
            weight = 1.0 / (1.0 + recent_counts.get(value_id, 0) * 2.0)
            if value_id in used_ids:
                weight *= 0.2
            weights.append(weight)
        return random.choices(available, weights=weights, k=1)[0]

    def _location_by_id(self, locations: list, location_id: int):
        try:
            normalized_id = int(location_id or 0)
        except (TypeError, ValueError):
            return None
        for location in locations:
            if getattr(location, "id", None) == normalized_id:
                return location
        return None

    def _generate_outing_candidate(self, outing, character, location, state: dict) -> dict:
        prompt = f"""
JSONのみを返してください。
おでかけミニイベントの後に出る、小さな世界ニュース/噂を1件作成してください。
私的な日記ではなく、都市の噂、目撃談、地域メモのように聞こえる内容にしてください。

必須キー:
{{"news_type":"outing_afterglow|character_sighting|relationship", "title":"...", "body":"...", "summary":"...", "importance":1-5}}

Romcom afterglow rules:
- Treat the outing aftermath as a witnessed love-comedy afterglow, not a neutral travel note.
- Add one concrete romantic-comedy tell: someone denied caring too fast, kept a gift/receipt, froze at accidental eye contact, got jealous, or was teased by witnesses.
- Keep it as public gossip/news with a small punchline, safe and non-explicit.
キャラクター: {character.name or ""}
キャラクター概要: {getattr(character, "character_summary", None) or ""}
キャラクター性格: {character.personality or ""}
場所: {location.name or ""}
場所説明: {location.description or ""}
おでかけタイトル: {outing.title or ""}
ムード: {outing.mood or ""}
記憶タイトル: {outing.memory_title or ""}
記憶概要: {outing.memory_summary or ""}
選択された選択肢: {json_util.dumps((state or {}).get("selected_choices") or [])}
""".strip()
        result = self._text_ai_client.generate_text(
            prompt,
            response_format={"type": "json_object"},
            temperature=0.75,
            max_tokens=700,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        return parsed if isinstance(parsed, dict) else self._fallback_outing_candidate(outing, character, location)

    def _fallback_candidates(self, project_id: int, count: int, *, plans: list[dict] | None = None) -> list[dict]:
        if plans:
            return [self._fallback_item_from_plan(plan) for plan in plans[:count]]
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
            "日本語キャラクター/世界観アプリ向けに、世界内ニュースらしい完成度の高い画像を作成してください。",
            "It should look like a modern local news card, not a plain illustration.",
            "Landscape 1536x1024, cinematic news photography with a clear news graphic layout.",
            "Make the image feel like a love-comedy scoop: awkward romantic distance, accidental eye contact, visible blushes, a jealous or teasing bystander, a misunderstood date-like moment, or a small public reaction that makes the rumor believable.",
            "Keep the tone playful, safe, and non-explicit; emphasize facial reactions, body language, props, and crowd response over exposure or sexual framing.",
            "リアルなエディトリアル写真、ドキュメンタリー/イベントニュース風の照明、自然なカメラ視点、説得力のある環境ディテールを使ってください。",
            "アニメイラスト、絵画調、ビジュアルノベルCG、セル塗り、漫画線画、キャラクターポスター風の構図は避けてください。",
            "左上に架空のニュースロゴ「LAPLACE NEWS」を入れてください。",
            "Include broadcast-style elements: top logo bar, lower-third headline strip, small category badge, subtle ticker-like decorative line.",
            "タイトルを元に、大きく読みやすい日本語見出しを使ってください。文字は短くし、長い段落は避けてください。",
            "実在の放送局ロゴ、実在の新聞ブランド、透かし、QRコード、UIスクリーンショットは使わないでください。",
            "画像には、都市、施設、キャラクター目撃、地域イベント、噂の空気など、報道されている場面そのものが見えるようにしてください。",
            "キャラクターの立ち絵だけに見える画像は避けてください。",
        ]
        if reference_characters:
            lines.extend(
                [
                    f"{len(reference_characters)} base character reference image(s) are provided.",
                    "提供された各キャラクター基準画像を、それぞれ別人の同一性参照として使ってください。",
                    "参照キャラクターごとに、顔の同一性、髪型、髪色、目の形、体の印象、全体のキャラクターデザインを維持してください。",
                    "ニュースのタイトル/本文に2人の参照キャラクターがいる場合は、両方を描き、別の2人目を創作しないでください。",
                    "参照画像は同一性のために使ってください。画像全体をイラスト調にする理由にはしないでください。参照がイラストでも、その同一性をリアルなニュース写真風へ変換してください。",
                    "サムネイル、アイコン、アバター、切り抜きポートレートを同一性参照として使わないでください。",
                    "基準画像の同一性を保ったまま、キャラクターをニュース場面へ自然に適応させてください。",
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
