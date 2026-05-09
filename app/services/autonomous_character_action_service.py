from __future__ import annotations

import random
from datetime import datetime

from ..clients.text_ai_client import TextAIClient
from ..models import FeedPost, WorldNewsItem
from ..repositories.character_repository import CharacterRepository
from ..repositories.feed_repository import FeedRepository
from ..repositories.world_location_repository import WorldLocationRepository
from ..repositories.world_news_repository import WorldNewsRepository
from ..utils import json_util
from .feed_service import FEED_DUO_POST_PATTERNS, FEED_POST_PATTERNS, FeedService
from .project_service import ProjectService
from .world_service import WorldService


ACTION_PATTERNS = [
    "施設で小さなトラブルを起こす",
    "誰かに目撃される",
    "店や仕事で新しい試みをする",
    "深夜に意味深な行動をする",
    "別キャラと小さなやり取りをする",
    "都市の噂になる",
    "うっかり本音が漏れる",
    "何かを観測、調査、記録する",
]

FALLBACK_ROMCOM_SCENES = [
    {
        "action_type": "unexpected romantic-comedy sighting",
        "feed_body": "{character}が{place}で、誰かに見られた瞬間だけ明らかに動揺していた。平静を装っているけど、耳まで赤い。",
        "news_title": "{place}で{character}の照れ隠し目撃情報",
        "news_body": "{place}で{character}が小さな誤解からラブコメめいた空気に巻き込まれていた、という目撃談が流れている。本人は何でもないふりをしていたが、周囲にはかなり分かりやすかったらしい。",
        "summary": "平静を装うほど照れが見える小さな目撃ログ。",
        "image_mood": "flustered but trying to act composed",
        "visual_hook": "caught making accidental eye contact, with a comedic witness in the background",
    },
    {
        "action_type": "near-miss date situation",
        "feed_body": "{character}が{place}で待ち合わせっぽい立ち位置にいて、通りすがりに見られた途端、なぜか言い訳を始めた。",
        "news_title": "{character}、{place}で待ち合わせ疑惑",
        "news_body": "{place}で{character}が誰かを待っているように見えたという噂が出ている。真相は不明だが、本人の反応だけを見ると何かを隠しているようにも見える。",
        "summary": "待ち合わせに見える状況で誤解が生まれたログ。",
        "image_mood": "embarrassed, defensive, secretly happy",
        "visual_hook": "standing under a sign or clock like a date meeting spot, holding a small item",
    },
    {
        "action_type": "small romantic mishap",
        "feed_body": "{character}が{place}で小さな失敗をして、助けてもらった後に妙に黙り込んでいた。これは多分、事件ではなく照れ。",
        "news_title": "{place}で{character}の小さなハプニング",
        "news_body": "{place}で{character}がささやかなハプニングに遭遇した。深刻なものではないが、その後の反応が妙に印象的だったため、周囲の話題になっている。",
        "summary": "助けられた後の照れが残る小さなハプニング。",
        "image_mood": "shy gratitude, caught off guard",
        "visual_hook": "almost-touching hands after someone helps pick up a dropped item",
    },
    {
        "action_type": "jealous romcom beat",
        "feed_body": "{character}が{place}で何気ない会話を聞いたあと、急にそっけなくなった。でも視線だけはずっと気にしている。",
        "news_title": "{character}、{place}で少し不機嫌そう",
        "news_body": "{place}で{character}が一瞬だけ嫉妬にも見える反応を見せたという。本人は否定しそうだが、表情はかなり正直だったらしい。",
        "summary": "嫉妬かもしれない表情が残ったラブコメ調のログ。",
        "image_mood": "jealous but pretending not to care",
        "visual_hook": "looking away with crossed arms while still glancing back",
    },
    {
        "action_type": "surprise close-distance moment",
        "feed_body": "{character}が{place}で不意に距離を詰められて、言葉を失っていた。数秒後に何もなかったことにしたのが逆に怪しい。",
        "news_title": "{place}で{character}の近距離ハプニング",
        "news_body": "{place}で{character}が予想外の近距離シチュエーションに遭遇した。短い出来事だったが、周囲にはかなりラブコメらしい瞬間として記憶された。",
        "summary": "近距離で不意打ちを受けた瞬間のログ。",
        "image_mood": "surprised, breathless, visibly flustered",
        "visual_hook": "dynamic close-distance framing with motion blur and warm rim light",
    },
]


class AutonomousCharacterActionService:
    def __init__(
        self,
        *,
        character_repository: CharacterRepository | None = None,
        location_repository: WorldLocationRepository | None = None,
        feed_repository: FeedRepository | None = None,
        news_repository: WorldNewsRepository | None = None,
        feed_service: FeedService | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        text_ai_client: TextAIClient | None = None,
    ):
        self._characters = character_repository or CharacterRepository()
        self._locations = location_repository or WorldLocationRepository()
        self._feed = feed_repository or FeedRepository()
        self._news = news_repository or WorldNewsRepository()
        self._feed_service = feed_service or FeedService(repository=self._feed)
        self._projects = project_service or ProjectService()
        self._worlds = world_service or WorldService()
        self._text_ai_client = text_ai_client or TextAIClient()

    def generate_actions(
        self,
        *,
        project_id: int,
        created_by_user_id: int | None = None,
        count: int = 3,
        target: str = "feed",
        status: str = "published",
        use_ai: bool = True,
        with_images: bool = False,
        image_size: str = "1536x1024",
        image_quality: str | None = None,
    ) -> dict:
        project = self._projects.get_project(project_id)
        if not project:
            raise LookupError("project not found")
        created_by_user_id = int(created_by_user_id or project.owner_user_id)
        count = max(1, min(int(count or 3), 10))
        target = self._normalize_target(target)
        status = "draft" if status == "draft" else "published"

        characters = self._characters.list_by_project(project_id)
        if not characters:
            raise ValueError("project has no characters")
        locations = self._locations.list_by_project(project_id)
        recent_context = self._recent_action_context(project_id)
        action_items = self._build_action_items(
            project=project,
            characters=characters,
            locations=locations,
            count=count,
            use_ai=use_ai,
            recent_context=recent_context,
        )

        created = []
        for item in action_items:
            character = self._valid_character(project_id, item.get("character_id")) or random.choice(characters)
            location = self._valid_location(project_id, item.get("location_id"))
            feed_post = None
            news_item = None
            if target in {"feed", "both"}:
                feed_post = self._create_feed_post(
                    project_id=project_id,
                    character_id=character.id,
                    created_by_user_id=created_by_user_id,
                    body=item.get("feed_body") or item.get("body") or self._fallback_feed_body(character, location),
                    status=status,
                    item=item,
                )
                if with_images:
                    item["image"] = self._generate_feed_image(
                        feed_post=feed_post,
                        character=character,
                        location=location,
                        item=item,
                        image_size=image_size,
                        image_quality=image_quality,
                    )
            if target in {"news", "both"}:
                news_item = self._create_news_item(
                    project_id=project_id,
                    character_id=character.id,
                    location_id=getattr(location, "id", None),
                    created_by_user_id=created_by_user_id,
                    item=item,
                    feed_post=feed_post,
                )
            created.append(
                {
                    "character_id": character.id,
                    "character_name": character.name,
                    "location_id": getattr(location, "id", None),
                    "location_name": getattr(location, "name", None),
                    "action_type": item.get("action_type") or "自律行動",
                    "post_pattern": item.get("post_pattern"),
                    "co_character_id": item.get("co_character_id"),
                    "feed_post_id": getattr(feed_post, "id", None),
                    "news_id": getattr(news_item, "id", None),
                    "feed_body": getattr(feed_post, "body", None),
                    "news_title": getattr(news_item, "title", None),
                    "image_asset_id": (item.get("image") or {}).get("image_asset_id"),
                    "image_error": (item.get("image") or {}).get("error"),
                }
            )
        return {"project_id": project_id, "target": target, "count": len(created), "items": created}

    def preview_actions(self, *, project_id: int, count: int = 3, use_ai: bool = True) -> dict:
        project = self._projects.get_project(project_id)
        if not project:
            raise LookupError("project not found")
        characters = self._characters.list_by_project(project_id)
        if not characters:
            raise ValueError("project has no characters")
        locations = self._locations.list_by_project(project_id)
        recent_context = self._recent_action_context(project_id)
        items = self._build_action_items(
            project=project,
            characters=characters,
            locations=locations,
            count=max(1, min(int(count or 3), 10)),
            use_ai=use_ai,
            recent_context=recent_context,
        )
        return {"project_id": project_id, "count": len(items), "items": items}

    def _build_action_items(
        self,
        *,
        project,
        characters: list,
        locations: list,
        count: int,
        use_ai: bool,
        recent_context: dict | None = None,
    ) -> list[dict]:
        recent_context = recent_context or {}
        target_characters = self._select_action_characters(characters, recent_context, count=count)
        action_plans = self._build_action_plans(
            target_characters,
            all_characters=characters,
            locations=locations,
        )
        if use_ai:
            try:
                items = self._generate_action_items(
                    project=project,
                    characters=target_characters,
                    all_characters=characters,
                    locations=locations,
                    count=count,
                    recent_context=recent_context,
                    action_plans=action_plans,
                )
                if items:
                    return self._diversify_action_items(
                        items[:count],
                        characters=target_characters,
                        locations=locations,
                        count=count,
                        recent_context=recent_context,
                        action_plans=action_plans,
                    )
            except Exception:
                pass
        return self._fallback_action_items(
            characters=target_characters,
            locations=locations,
            count=count,
            avoid_character_ids=set(recent_context.get("recent_character_ids") or []),
            avoid_action_types=set(recent_context.get("recent_action_types") or []),
            action_plans=action_plans,
        )

    def _generate_action_items(
        self,
        *,
        project,
        characters: list,
        all_characters: list,
        locations: list,
        count: int,
        recent_context: dict | None = None,
        action_plans: list[dict] | None = None,
    ) -> list[dict]:
        world = self._worlds.get_world(project.id)
        recent_context = recent_context or {}
        run_seed = random.randint(100000, 999999)
        selected_ids = [character.id for character in characters]
        prompt = f"""
JSONのみを返してください。
ラプラスシティのキャラクターが、ユーザー操作なしに自律的に少し動いたログを {count} 件作成してください。

必須形式:
{{"items":[{{"character_id": 1, "location_id": null or 2, "action_type":"...", "feed_body":"...", "news_title":"...", "news_body":"...", "summary":"...", "importance":1-5, "image_mood":"...", "visual_hook":"..."}}]}}

多様性ルール:
- 必ず {count} 件返す。
- character_id は次の対象IDだけを使い、それぞれ1件ずつ作る: {json_util.dumps(selected_ids)}
- action_type、feed_body、image_mood、visual_hook は各件で必ず変える。
- 汎用的な日常報告ではなく、事件、目撃、引用、投票、変な告知、小スキャンダル、恋愛ハプニング、食べ物事故、施設トラブル、オチのどれかを入れる。
- 同じ文型や同じオチを繰り返さない。

ルール:
- 日本語のみ。
- feed_body はキャラクター本人の投稿、目撃情報、街の短いログのどれかにする。80〜180文字。
- news_title は短く、ニュースや噂の見出しにする。
- news_body は100〜220文字。
- 大事件や不可逆な破壊は起こさない。日常の小さな変化、噂、目撃、仕事、照れ、観測、失敗にする。
- キャラクターの性格、口調、役割を反映する。
- 提供された character_id / location_id だけを使う。
- location_id は場所が自然な場合だけ使い、不要なら null。
- 既存の会話結果を断定せず、次に話題にできる余白を残す。
- action_plan の post_pattern と pattern_instruction に必ず従う。
- action_plan に co_character がある場合、その共演キャラとの関係ややり取りを本文に含める。ただし主役は対象 character_id のキャラにする。
- 何が起きた、どこで起きた、なぜ変なのか、最後のオチがつながるようにする。
- 抽象的な造語ではなく、看板、自販機、椅子、マイク、扉、照明、メニュー、端末など具体物で笑わせる。
- image_mood は表情を、visual_hook は写真に写る具体的な構図や小道具を指定する。

Romcom density for feed/news:
- Push each generated action toward a stronger love-comedy beat than a normal daily log.
- Prefer visible tells: blushing, defensive denial, awkward silence, accidental eye contact, jealousy, protectiveness, almost-confessions, misunderstood date-like timing, or witnesses teasing them.
- feed_body should feel immediate and character/post-like; news_title/news_body should feel like public rumor coverage of the same incident.
- Keep it playful and non-explicit. Convert suggestive material into safe romantic tension, boundaries, fashion mishaps, crowd reactions, or awkward timing.
プロジェクト: {project.title or ""}
プロジェクト概要: {project.summary or ""}
世界観概要: {getattr(world, "overview", "") if world else ""}
世界観トーン: {getattr(world, "tone", "") if world else ""}
今回の生成シード: {run_seed}
キャラクター: {json_util.dumps([self._character_context(c) for c in characters])}
共演候補キャラクター: {json_util.dumps([self._character_context(c) for c in all_characters[:30]])}
場所: {json_util.dumps([self._location_context(l) for l in locations])}
行動パターン候補: {json_util.dumps(ACTION_PATTERNS)}
今回のaction_plan: {json_util.dumps(action_plans or [])}
直近の自律行動ログ（これらの character_id / action_type / feed_body と似せない）: {json_util.dumps(recent_context.get("recent_items") or [])}
""".strip()
        result = self._text_ai_client.generate_text(
            prompt,
            response_format={"type": "json_object"},
            temperature=0.85,
            max_tokens=1800,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        items = parsed.get("items") if isinstance(parsed, dict) else []
        if not isinstance(items, list):
            return []
        return [self._normalize_item(item) for item in items if isinstance(item, dict)]

    def _select_action_characters(self, characters: list, recent_context: dict, *, count: int) -> list:
        available = [character for character in characters if getattr(character, "id", None)]
        if not available:
            return []
        recent_ids = [int(value) for value in (recent_context.get("recent_character_ids") or []) if int(value or 0)]
        recent_counts = {character.id: recent_ids.count(character.id) for character in available}
        latest_index = {}
        for index, character_id in enumerate(recent_ids):
            latest_index.setdefault(character_id, index)
        jitter = {character.id: random.random() for character in available}
        ranked = sorted(
            available,
            key=lambda character: (
                recent_counts.get(character.id, 0),
                latest_index.get(character.id, -1) >= 0,
                -latest_index.get(character.id, -1),
                jitter.get(character.id, 0),
            ),
        )
        desired_count = max(1, int(count or 1))
        if desired_count <= len(ranked):
            return ranked[:desired_count]
        return self._cycled_shuffle(ranked, desired_count)

    def _build_action_plans(self, characters: list, *, all_characters: list, locations: list) -> list[dict]:
        if not characters:
            return []
        patterns = random.sample(FEED_POST_PATTERNS, k=min(len(characters), len(FEED_POST_PATTERNS)))
        if len(patterns) < len(characters):
            patterns.extend(random.choice(FEED_POST_PATTERNS) for _ in range(len(characters) - len(patterns)))
        all_candidates = [character for character in (all_characters or characters) if getattr(character, "id", None)]
        location_order = self._cycled_shuffle(locations, len(characters)) if locations else [None] * len(characters)
        plans = []
        for index, (character, pattern) in enumerate(zip(characters, patterns)):
            use_duo = len(all_candidates) >= 2 and random.random() < 0.45
            co_character = None
            if use_duo:
                partners = [candidate for candidate in all_candidates if int(candidate.id) != int(character.id)]
                co_character = random.choice(partners) if partners else None
                pattern = random.choice(FEED_DUO_POST_PATTERNS)
            location = location_order[index]
            plans.append(
                {
                    "character_id": character.id,
                    "character_name": getattr(character, "name", "") or "",
                    "post_pattern": pattern["name"],
                    "pattern_instruction": pattern["instruction"],
                    "location_id": getattr(location, "id", None),
                    "location_name": getattr(location, "name", None),
                    "co_character_id": getattr(co_character, "id", None) if co_character else None,
                    "co_character_name": getattr(co_character, "name", None) if co_character else None,
                    "co_character": self._character_context(co_character) if co_character else None,
                    "image_mood": random.choice(
                        [
                            "flustered but trying to act composed",
                            "smug until the punchline lands",
                            "jealous but pretending not to care",
                            "surprised and caught mid-reaction",
                            "shy happy, defensive, and visibly embarrassed",
                            "deadpan while the background is chaotic",
                        ]
                    ),
                    "visual_hook": random.choice(
                        [
                            "a concrete prop in the foreground reveals the joke",
                            "a signboard or menu makes the misunderstanding obvious",
                            "the co-character reacts in the background while the main character tries to stay composed",
                            "almost-touching hands, awkward distance, and one visible comedic witness",
                            "a failed photo pose with one strange object clearly visible",
                            "motion blur from the exact moment the incident happened",
                        ]
                    ),
                }
            )
        return plans

    def _fallback_action_items(
        self,
        *,
        characters: list,
        locations: list,
        count: int,
        avoid_character_ids: set[int] | None = None,
        avoid_action_types: set[str] | None = None,
        action_plans: list[dict] | None = None,
    ) -> list[dict]:
        items = []
        avoid_character_ids = avoid_character_ids or set()
        avoid_action_types = avoid_action_types or set()
        preferred_characters = [character for character in characters if character.id not in avoid_character_ids] or characters
        preferred_scenes = [scene for scene in FALLBACK_ROMCOM_SCENES if scene.get("action_type") not in avoid_action_types] or FALLBACK_ROMCOM_SCENES
        character_order = self._cycled_shuffle(preferred_characters, count)
        location_order = self._cycled_shuffle(locations, count) if locations else [None] * count
        scene_order = self._cycled_shuffle(preferred_scenes, count)
        action_order = self._cycled_shuffle(ACTION_PATTERNS, count)
        plans_by_character_id = {
            int(plan.get("character_id")): plan
            for plan in (action_plans or [])
            if plan.get("character_id")
        }
        for index in range(count):
            character = character_order[index]
            location = location_order[index]
            scene = scene_order[index]
            plan = plans_by_character_id.get(int(character.id), {})
            if plan.get("location_id"):
                location = self._valid_location(getattr(character, "project_id", 0), plan.get("location_id")) or location
            action_type = scene.get("action_type") or action_order[index]
            if plan.get("post_pattern"):
                action_type = plan["post_pattern"]
            place = getattr(location, "name", None) or "街のどこか"
            co_name = plan.get("co_character_name")
            co_tail = f" 共演: {co_name}。" if co_name else ""
            items.append(
                {
                    "character_id": character.id,
                    "location_id": getattr(location, "id", None),
                    "action_type": action_type,
                    "feed_body": scene["feed_body"].format(character=character.name, place=place) + co_tail,
                    "news_title": scene["news_title"].format(character=character.name, place=place),
                    "news_body": scene["news_body"].format(character=character.name, place=place) + co_tail,
                    "summary": scene["summary"],
                    "post_pattern": plan.get("post_pattern"),
                    "co_character_id": plan.get("co_character_id"),
                    "image_mood": scene["image_mood"],
                    "visual_hook": plan.get("visual_hook") or scene["visual_hook"],
                    "importance": 3,
                }
            )
        return items

    def _diversify_action_items(
        self,
        items: list[dict],
        *,
        characters: list,
        locations: list,
        count: int,
        recent_context: dict | None = None,
        action_plans: list[dict] | None = None,
    ) -> list[dict]:
        recent_context = recent_context or {}
        diversified = [dict(item or {}) for item in items[:count]]
        while len(diversified) < count:
            diversified.extend(
                self._fallback_action_items(
                    characters=characters,
                    locations=locations,
                    count=count - len(diversified),
                    avoid_character_ids=set(recent_context.get("recent_character_ids") or []),
                    avoid_action_types=set(recent_context.get("recent_action_types") or []),
                    action_plans=action_plans,
                )
            )

        project_id = getattr(characters[0], "project_id", 0) if characters else 0
        recent_character_ids = set(recent_context.get("recent_character_ids") or [])
        preferred_characters = [character for character in characters if character.id not in recent_character_ids] or characters
        character_cycle = self._cycled_shuffle(preferred_characters, count)
        location_cycle = self._cycled_shuffle(locations, count) if locations else [None] * count
        used_character_ids = set()
        used_fingerprints = set(recent_context.get("recent_fingerprints") or [])
        recent_action_types = set(recent_context.get("recent_action_types") or [])

        for index, item in enumerate(diversified[:count]):
            current_character = self._valid_character(project_id, item.get("character_id"))
            if (
                not current_character
                or (
                    len(used_character_ids) < len(characters)
                    and current_character.id in used_character_ids
                )
                or (
                    len(recent_character_ids) < len(characters)
                    and current_character.id in recent_character_ids
                )
            ):
                current_character = self._first_unused_character(character_cycle, used_character_ids) or character_cycle[index]
                item["character_id"] = current_character.id
            used_character_ids.add(current_character.id)

            if location_cycle[index] and not self._valid_location(project_id, item.get("location_id")):
                item["location_id"] = getattr(location_cycle[index], "id", None)

            fingerprint = self._item_fingerprint(item)
            if fingerprint in used_fingerprints or item.get("action_type") in recent_action_types:
                fallback = self._fallback_action_items(
                    characters=[current_character],
                    locations=locations,
                    count=1,
                    avoid_action_types=recent_action_types,
                    action_plans=action_plans,
                )[0]
                item.update({key: value for key, value in fallback.items() if key not in {"character_id", "location_id"} or not item.get(key)})
                fingerprint = self._item_fingerprint(item)
            used_fingerprints.add(fingerprint)

        return diversified[:count]

    def _cycled_shuffle(self, values: list, count: int) -> list:
        if not values:
            return []
        result = []
        while len(result) < count:
            chunk = list(values)
            random.shuffle(chunk)
            result.extend(chunk)
        return result[:count]

    def _first_unused_character(self, characters: list, used_character_ids: set[int]):
        for character in characters:
            if character.id not in used_character_ids:
                return character
        return None

    def _item_fingerprint(self, item: dict) -> str:
        return "|".join(
            str(item.get(key) or "").strip().lower()
            for key in ("action_type", "feed_body", "news_title", "summary")
        )

    def _recent_action_context(self, project_id: int, limit: int = 24) -> dict:
        posts = self._feed.list_posts(project_id=project_id, statuses=["published", "draft"], limit=limit)
        recent_items = []
        recent_character_ids = []
        recent_action_types = []
        recent_fingerprints = []
        for post in posts:
            if not post.generation_state_json:
                continue
            try:
                state = json_util.loads(post.generation_state_json) or {}
            except (TypeError, ValueError):
                continue
            if state.get("source") != "autonomous_character_action":
                continue
            raw_item = state.get("raw_item") if isinstance(state.get("raw_item"), dict) else {}
            item = {
                "character_id": post.character_id,
                "action_type": state.get("action_type") or raw_item.get("action_type"),
                "feed_body": post.body,
                "summary": raw_item.get("summary"),
                "image_mood": raw_item.get("image_mood"),
                "visual_hook": raw_item.get("visual_hook"),
            }
            recent_items.append(item)
            recent_character_ids.append(post.character_id)
            if item["action_type"]:
                recent_action_types.append(str(item["action_type"]))
            recent_fingerprints.append(self._item_fingerprint(item))
        return {
            "recent_items": recent_items[:12],
            "recent_character_ids": recent_character_ids[:12],
            "recent_action_types": recent_action_types[:12],
            "recent_fingerprints": recent_fingerprints[:12],
        }

    def _create_feed_post(
        self,
        *,
        project_id: int,
        character_id: int,
        created_by_user_id: int,
        body: str,
        status: str,
        item: dict,
    ) -> FeedPost:
        return self._feed.create_post(
            {
                "project_id": project_id,
                "character_id": character_id,
                "created_by_user_id": created_by_user_id,
                "body": str(body or "").strip()[:2000] or "今日は少しだけ街を歩いた。",
                "status": status,
                "generation_state_json": json_util.dumps(
                    {
                        "source": "autonomous_character_action",
                        "action_type": item.get("action_type"),
                        "generated_at": datetime.utcnow().isoformat(),
                        "raw_item": item,
                    }
                ),
            }
        )

    def _create_news_item(
        self,
        *,
        project_id: int,
        character_id: int,
        location_id: int | None,
        created_by_user_id: int,
        item: dict,
        feed_post: FeedPost | None,
    ) -> WorldNewsItem:
        return self._news.create(
            {
                "project_id": project_id,
                "created_by_user_id": created_by_user_id,
                "related_character_id": character_id,
                "related_location_id": location_id,
                "news_type": "character_sighting",
                "title": str(item.get("news_title") or "キャラクターの目撃情報").strip()[:255],
                "body": str(item.get("news_body") or item.get("feed_body") or "").strip()[:2000],
                "summary": str(item.get("summary") or "").strip()[:500] or None,
                "importance": max(1, min(5, int(item.get("importance") or 3))),
                "source_type": "autonomous_character_action",
                "source_ref_type": "feed_post" if feed_post else "character",
                "source_ref_id": getattr(feed_post, "id", None) or character_id,
                "return_url": "/feed" if feed_post else f"/projects/{project_id}/world-news",
                "status": "published",
                "metadata_json": json_util.dumps(
                    {
                        "source": "autonomous_character_action",
                        "action_type": item.get("action_type"),
                        "feed_post_id": getattr(feed_post, "id", None),
                        "generated_at": datetime.utcnow().isoformat(),
                        "raw_item": item,
                    }
                ),
            }
        )

    def _generate_feed_image(
        self,
        *,
        feed_post: FeedPost,
        character,
        location,
        item: dict,
        image_size: str,
        image_quality: str | None,
    ) -> dict:
        prompt = self._build_romcom_photo_prompt(feed_post=feed_post, character=character, location=location, item=item)
        try:
            updated = self._feed_service.generate_post_image(
                feed_post.id,
                {
                    "prompt": prompt,
                    "size": image_size,
                    **({"quality": image_quality} if image_quality else {}),
                },
            )
        except Exception as exc:
            return {"status": "error", "error": str(exc)[:500], "prompt": prompt}
        return {
            "status": "success",
            "feed_post_id": feed_post.id,
            "image_asset_id": getattr(updated, "image_asset_id", None),
            "prompt": prompt,
        }

    def _build_romcom_photo_prompt(self, *, feed_post: FeedPost, character, location, item: dict) -> str:
        place = getattr(location, "name", None) or "街のどこか"
        action_type = str(item.get("action_type") or "キャラクター自律行動").strip()
        return "\n".join(
            [
                "Create a high-impact romantic-comedy candid photo for a character world app.",
                "Use any provided reference image as the primary source of the character's identity, face, hair, outfit design logic, coloring, and rendering style.",
                "No text, no captions, no speech bubbles, no UI, no logo, no watermark.",
                "The image should feel like a dramatic social-media sighting photo or visual novel event CG, not a plain portrait.",
                "Make the character's emotion immediately readable: flustered, embarrassed, surprised, jealous, shyly happy, trying to act composed, or caught off guard.",
                "Prioritize love-comedy energy: awkward romantic distance, accidental eye contact, almost-touching hands, a misunderstood date-like situation, a comedic background witness, or a small romantic mishap.",
                "Keep it tasteful and non-explicit. Fully clothed characters, romantic tension through expression, posture, lighting, and staging rather than sexual content.",
                "Use cinematic photography: dynamic angle, foreground obstruction, warm rim light, shallow depth of field, motion blur, visible evidence of what just happened.",
                "The viewer should understand the incident and emotion from the image alone.",
                f"Main character: {getattr(character, 'name', '') or ''}",
                f"Character overview: {getattr(character, 'character_summary', '') or ''}",
                f"Personality: {getattr(character, 'personality', '') or ''}",
                f"Appearance: {getattr(character, 'appearance_summary', '') or ''}",
                f"Art style: {getattr(character, 'art_style', '') or ''}",
                f"Location: {place}",
                f"Action type: {action_type}",
                f"Feed post body / situation: {feed_post.body}",
                f"News-like summary: {item.get('summary') or ''}",
                f"Emotional mood: {item.get('image_mood') or ''}",
                f"Distinct visual hook: {item.get('visual_hook') or ''}",
                "Composition idea: caught in the middle of the action, with the romantic-comedy misunderstanding visible in the environment.",
            ]
        )

    def _normalize_item(self, item: dict) -> dict:
        normalized = dict(item or {})
        normalized["feed_body"] = str(normalized.get("feed_body") or normalized.get("body") or "").strip()
        normalized["news_title"] = str(normalized.get("news_title") or normalized.get("title") or "").strip()
        normalized["news_body"] = str(normalized.get("news_body") or normalized.get("body") or "").strip()
        normalized["summary"] = str(normalized.get("summary") or "").strip()
        normalized["image_mood"] = str(normalized.get("image_mood") or "").strip()
        normalized["visual_hook"] = str(normalized.get("visual_hook") or "").strip()
        normalized["post_pattern"] = str(normalized.get("post_pattern") or "").strip()
        try:
            normalized["co_character_id"] = int(normalized.get("co_character_id") or 0) or None
        except (TypeError, ValueError):
            normalized["co_character_id"] = None
        try:
            normalized["importance"] = max(1, min(5, int(normalized.get("importance") or 3)))
        except (TypeError, ValueError):
            normalized["importance"] = 3
        return normalized

    def _normalize_target(self, target: str) -> str:
        value = str(target or "feed").strip().lower()
        if value not in {"feed", "news", "both"}:
            raise ValueError("target must be feed, news, or both")
        return value

    def _valid_character(self, project_id: int, value):
        try:
            character_id = int(value or 0)
        except (TypeError, ValueError):
            return None
        character = self._characters.get(character_id)
        return character if character and character.project_id == project_id else None

    def _valid_location(self, project_id: int, value):
        try:
            location_id = int(value or 0)
        except (TypeError, ValueError):
            return None
        location = self._locations.get(location_id)
        return location if location and location.project_id == project_id else None

    def _fallback_feed_body(self, character, location) -> str:
        place = getattr(location, "name", None) or "街のどこか"
        return f"{character.name}が{place}で少しだけ動いていた。大きな事件ではないけれど、街には小さな痕跡が残った。"

    def _character_context(self, character) -> dict:
        return {
            "id": character.id,
            "name": character.name,
            "nickname": character.nickname,
            "summary": character.character_summary,
            "personality": character.personality,
            "speech_style": character.speech_style,
            "first_person": character.first_person,
        }

    def _location_context(self, location) -> dict:
        return {
            "id": location.id,
            "name": location.name,
            "region": location.region,
            "location_type": location.location_type,
            "description": location.description,
        }
