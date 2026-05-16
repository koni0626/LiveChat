from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
import mimetypes
import os
import random
import re
import socket
import uuid
from collections import Counter
from datetime import datetime, timedelta
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from flask import current_app
import requests

from ..clients.image_ai_client import ImageAIClient
from ..clients.text_ai_client import TextAIClient
from ..extensions import db
from ..models.feed_x_schedule import FeedXSchedule
from ..repositories.character_outfit_repository import CharacterOutfitRepository
from ..repositories.feed_repository import FeedRepository
from ..repositories.world_location_repository import WorldLocationRepository
from ..utils import json_util
from .asset_service import AssetService
from .character_service import CharacterService
from .project_service import ProjectService
from .world_service import WorldService
from .x_publishing_service import XPublishingService


FEED_POST_PATTERNS = [
    {
        "name": "速報・事件型",
        "instruction": "【速報】や【発生】のように、ラプラスシティで小事件が起きた体裁で書く。原因、現場、キャラの反応、オチを入れる。",
    },
    {
        "name": "炎上しかけ型",
        "instruction": "キャラの発言や行動が少し物議を呼びそうな体裁で書く。重くしすぎず、ツッコミで落とす。",
    },
    {
        "name": "目撃情報型",
        "instruction": "誰かがキャラを見かけたような投稿にする。場所、変な行動、最後の一言で笑いを作る。",
    },
    {
        "name": "ゆるい事故報告型",
        "instruction": "施設、発明、料理、業務などで軽い事故が起きた報告にする。大惨事ではなく笑えるトラブルにする。",
    },
    {
        "name": "キャラの自爆投稿型",
        "instruction": "キャラ本人が勢いで投稿して、うっかり本音や恥ずかしい情報が漏れる形にする。",
    },
    {
        "name": "意味深ポエムからのオチ型",
        "instruction": "最初は少し美しい、意味深な文章にして、最後にしょうもない現実やキャラの失敗で落とす。",
    },
    {
        "name": "アンケート型",
        "instruction": "Xの投票風に、3択か4択の選択肢を出す。選択肢自体で笑えるようにする。",
    },
    {
        "name": "引用RT風ツッコミ型",
        "instruction": "引用元の短い発言を先に置き、それに対してツッコむ。引用元はキャラ本人、施設、都市放送などでよい。",
    },
    {
        "name": "現地レポ型",
        "instruction": "現場からレポートしている体裁で書く。目の前で起きている異常とキャラの反応を短く伝える。",
    },
    {
        "name": "怪文書型",
        "instruction": "一見まじめなお知らせや注意喚起なのに内容が変な文章にする。都市の公式注意文っぽくしてよい。",
    },
    {
        "name": "キャラ同士の小競り合い型",
        "instruction": "2人以上の短い会話ログ風にする。言い合い、勘違い、商談、恋愛の茶化しなどでテンポを作る。",
    },
    {
        "name": "お知らせなのに変型",
        "instruction": "公式お知らせ風に始めて、条件や注意事項が変すぎる形で笑いを作る。",
    },
    {
        "name": "デートスポット異常型",
        "instruction": "デート施設で妙な仕様やイベントが発生した体裁で書く。恋愛の気まずさや照れを混ぜる。",
    },
    {
        "name": "キャラの本音漏れ型",
        "instruction": "キャラのかわいい弱点、本音、照れ、見栄が漏れた目撃情報にする。茶化しすぎず愛嬌を残す。",
    },
    {
        "name": "都市伝説型",
        "instruction": "ラプラスシティで囁かれる都市伝説風にする。噂の正体や勘違いの原因を本文内で推測し、最後に実在しそうな怖さより笑いを残す。",
    },
    {
        "name": "業務連絡風コメディ型",
        "instruction": "業務連絡や注意事項の形で、現場が混乱している様子を出す。短く、事務的な文体と内容の落差で笑わせる。",
    },
    {
        "name": "失敗写真の添え文型",
        "instruction": "写真付き投稿のキャプション風に書く。映えを狙ったのに変なものが写った、という方向で作る。",
    },
    {
        "name": "小さな恋愛事件型",
        "instruction": "恋愛っぽい一瞬を事件のように書く。照れ、距離感、都市AIの過剰反応などを入れる。",
    },
    {
        "name": "食べ物事故型",
        "instruction": "料理、屋台、スイーツ、謎メニューなどで起きた事件にする。食レポとツッコミを混ぜる。",
    },
    {
        "name": "キャラ別名物ネタ型",
        "instruction": "そのキャラ固有の持ちネタ、職業、口調、弱点、好きなものを中心にした短い事件投稿にする。",
    },
]

FEED_DUO_POST_PATTERNS = [
    {
        "name": "キャラ同士の小競り合い型",
        "instruction": "メインキャラと共演キャラの短い言い合い、勘違い、商談、観測、採点、暴露などでテンポを作る。",
    },
    {
        "name": "目撃された二人型",
        "instruction": "二人が同じ場所で変な行動をしている目撃情報にする。どちらが何をしたかを明確にする。",
    },
    {
        "name": "共同事故報告型",
        "instruction": "二人で施設、料理、装置、イベントを扱った結果、軽い事故が起きた報告にする。",
    },
    {
        "name": "片方が巻き込まれる型",
        "instruction": "メインキャラが何かを始め、共演キャラが巻き込まれてツッコむ形にする。",
    },
    {
        "name": "恋愛茶化し型",
        "instruction": "二人の距離感、照れ、誤解、周囲の過剰反応を小さな恋愛事件として書く。",
    },
]

PHOTOBOOK_SCENE_PRESETS = [
    {
        "label": "夕暮れの神社",
        "message": "夕暮れ時の{character}。",
        "place_prompt": "a quiet old Japanese shrine terrace at sunset, warm lantern light, cherry blossoms, wooden railings, soft petals in the air",
    },
    {
        "label": "朝の花畑",
        "message": "朝の花畑にいる{character}。",
        "place_prompt": "a bright flower field in the early morning, gentle sunlight, fresh green grass, pastel flowers, shallow depth of field",
    },
    {
        "label": "雨上がりの路地",
        "message": "雨上がりの{character}。",
        "place_prompt": "a quiet narrow street after rain, glossy pavement, soft reflections, hydrangeas, clean fresh air, subtle city lights",
    },
    {
        "label": "海辺の午後",
        "message": "海辺で風に吹かれる{character}。",
        "place_prompt": "a calm seaside promenade in the afternoon, blue sky, sparkling ocean, white clouds, gentle wind",
    },
    {
        "label": "夜桜",
        "message": "夜桜と{character}。",
        "place_prompt": "night cherry blossoms, soft paper lanterns, elegant bokeh, quiet path, romantic but wholesome atmosphere",
    },
    {
        "label": "木漏れ日の縁側",
        "message": "木漏れ日の{character}。",
        "place_prompt": "a traditional veranda with dappled sunlight through trees, calm garden, soft shadows, warm peaceful mood",
    },
    {
        "label": "放課後の教室",
        "message": "放課後の{character}。",
        "place_prompt": "a quiet classroom after school, warm late-afternoon light through windows, tidy desks, soft dust motes, gentle nostalgic mood",
    },
    {
        "label": "駅前の夕景",
        "message": "夕方の駅前にいる{character}。",
        "place_prompt": "a small station plaza at golden hour, soft city lights, crosswalk reflections, calm everyday atmosphere, cinematic bokeh",
    },
    {
        "label": "図書館の窓辺",
        "message": "図書館の窓辺の{character}。",
        "place_prompt": "a quiet library window seat, tall bookshelves, soft natural light, warm wood textures, peaceful refined mood",
    },
    {
        "label": "星空の丘",
        "message": "星空の下の{character}。",
        "place_prompt": "a grassy hill under a clear starry sky, soft moonlight, distant town lights, dreamy but clean photobook atmosphere",
    },
    {
        "label": "夏祭りの屋台通り",
        "message": "夏祭りの{character}。",
        "place_prompt": "a summer festival street with food stalls, paper lanterns, warm night lighting, colorful bokeh, festive but gentle mood",
    },
    {
        "label": "温室の花園",
        "message": "温室にいる{character}。",
        "place_prompt": "a glasshouse botanical garden, lush greenery, tropical flowers, filtered sunlight, glass reflections, fresh elegant mood",
    },
    {
        "label": "雪の日の参道",
        "message": "雪の日の{character}。",
        "place_prompt": "a shrine approach covered in soft snow, red torii gate, white breath in cold air, quiet winter light, elegant atmosphere",
    },
    {
        "label": "カフェの窓際",
        "message": "カフェの窓際の{character}。",
        "place_prompt": "a cozy cafe window seat, soft morning light, simple table, warm drinks, muted city street outside, clean lifestyle photobook mood",
    },
    {
        "label": "屋上の青空",
        "message": "屋上の{character}。",
        "place_prompt": "a school or city rooftop under a vivid blue sky, white clouds, gentle wind, bright clean sunlight, open airy composition",
    },
    {
        "label": "水族館の光",
        "message": "水族館の光に包まれた{character}。",
        "place_prompt": "an aquarium hall with blue water glow, drifting light caustics, large glass tank, quiet magical atmosphere, soft reflections",
    },
    {
        "label": "和室の朝",
        "message": "朝の和室にいる{character}。",
        "place_prompt": "a simple traditional Japanese room in morning light, tatami mats, shoji screens, small flower arrangement, calm clean mood",
    },
    {
        "label": "イルミネーション通り",
        "message": "イルミネーションの{character}。",
        "place_prompt": "a winter illumination street, sparkling lights, soft night bokeh, elegant coat-friendly atmosphere, romantic but wholesome mood",
    },
    {
        "label": "森の小道",
        "message": "森の小道の{character}。",
        "place_prompt": "a quiet forest path, soft green light through leaves, mossy stones, gentle breeze, natural fairytale photobook feeling",
    },
    {
        "label": "美術館の回廊",
        "message": "美術館にいる{character}。",
        "place_prompt": "a modern art museum corridor, clean white walls, soft skylight, polished floor reflections, minimal elegant composition",
    },
    {
        "label": "夕焼けの河川敷",
        "message": "夕焼けの河川敷にいる{character}。",
        "place_prompt": "a riverside path at sunset, orange sky, calm water reflections, tall grass, gentle wind, nostalgic photobook mood",
    },
    {
        "label": "月明かりの庭",
        "message": "月明かりの庭にいる{character}。",
        "place_prompt": "a quiet Japanese garden under moonlight, stone lantern, dark pond reflections, subtle flowers, refined dreamy atmosphere",
    },
]

PHOTOBOOK_OUTFIT_PRESETS = [
    "a clean white shrine-maiden inspired outfit with delicate cords, beads, subtle red accents, layered flowing fabric",
    "a pale one-piece dress with soft translucent sleeves, ribbon details, tasteful elegant accessories",
    "a light kimono-inspired casual outfit, floral pattern, relaxed sash, delicate hair ornament",
    "a simple cream blouse and long skirt, airy fabric, small necklace, natural cute styling",
    "a soft cardigan over a modest dress, pastel color accents, gentle everyday photobook styling",
]

PHOTOBOOK_FRAMING_PRESETS = [
    "full-body portrait with clean magazine-like framing",
    "knees-up portrait with the background softly visible",
    "waist-up portrait with elegant negative space",
    "close portrait with cinematic shallow depth of field",
    "wide environmental portrait, character small enough to show the location",
    "three-quarter portrait with soft foreground bokeh",
    "profile-oriented portrait with gentle side light",
    "low-angle full-body portrait, airy sky or ceiling space",
    "high-angle seated portrait, delicate photobook composition",
    "over-the-shoulder environmental portrait, subtle and not too dramatic",
]

PHOTOBOOK_POSE_PRESETS = [
    "standing relaxed with one hand lightly touching the hair",
    "walking slowly, hair and clothing moving in a gentle breeze",
    "sitting on a bench or step with a calm posture",
    "leaning lightly against a railing or wall",
    "standing with both hands loosely behind the back",
    "holding a small seasonal prop naturally, not posing too hard",
    "looking up at the scenery with a quiet posture",
    "touching a flower, leaf, book, cup, or nearby object with one hand",
    "resting elbows lightly on a windowsill or railing",
    "standing in profile with a graceful straight posture",
    "crouching slightly to look at something near the ground",
    "sitting sideways with legs together and relaxed shoulders",
    "turning only slightly toward the camera, no exaggerated twist",
    "adjusting a sleeve, ribbon, hair ornament, or accessory",
    "hands clasped loosely in front, composed and clean",
    "one hand shading the eyes from light, natural outdoor pose",
    "walking down steps carefully, elegant everyday motion",
    "standing still while fabric moves in the wind",
]

PHOTOBOOK_GAZE_PRESETS = [
    "eyes toward camera",
    "looking slightly away from camera",
    "looking down softly",
    "looking up toward light or scenery",
    "side glance with a calm mood",
    "eyes following something in the background",
    "gaze lowered in a quiet photobook moment",
    "looking at the object in hand",
]

PHOTOBOOK_EXPRESSION_PRESETS = [
    "gentle smile",
    "soft neutral expression",
    "faint shy smile",
    "calm elegant expression",
    "slightly curious expression",
    "peaceful relaxed face",
    "bright but restrained smile",
    "cool composed expression",
    "dreamy distant expression",
    "small playful smile",
]

PHOTOBOOK_CAPTION_PRESETS = [
    "今日の{character}。",
    "やわらかい光の{character}。",
    "ただ可愛い{character}。",
    "きれいな{character}。",
    "少しだけ特別な{character}。",
    "光の中の{character}。",
    "{character}の一枚。",
    "静かな{character}。",
    "ふわっと{character}。",
    "透明感のある{character}。",
    "今日も可愛い{character}。",
    "綺麗めの{character}。",
    "何気ない{character}。",
    "写真集っぽい{character}。",
    "ただ眺めたい{character}。",
    "淡い雰囲気の{character}。",
]


class _MetaTagParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta":
            return
        attr_map = {str(key).lower(): value for key, value in attrs}
        key = attr_map.get("property") or attr_map.get("name")
        content = attr_map.get("content")
        if key and content:
            self.meta[str(key).strip().lower()] = unescape(str(content).strip())


class FeedService:
    VALID_STATUSES = {"draft", "published", "archived"}

    def __init__(
        self,
        repository: FeedRepository | None = None,
        asset_service: AssetService | None = None,
        character_service: CharacterService | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        location_repository: WorldLocationRepository | None = None,
        outfit_repository: CharacterOutfitRepository | None = None,
        text_ai_client: TextAIClient | None = None,
        image_ai_client: ImageAIClient | None = None,
        x_publishing_service: XPublishingService | None = None,
    ):
        self._repo = repository or FeedRepository()
        self._asset_service = asset_service or AssetService()
        self._character_service = character_service or CharacterService()
        self._project_service = project_service or ProjectService()
        self._world_service = world_service or WorldService()
        self._locations = location_repository or WorldLocationRepository()
        self._outfits = outfit_repository or CharacterOutfitRepository()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._image_ai_client = image_ai_client or ImageAIClient()
        self._x_publishing_service = x_publishing_service or XPublishingService(asset_service=self._asset_service)

    def _media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        if not normalized_path.startswith(normalized_root):
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"

    def _serialize_asset(self, asset):
        if not asset:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "mime_type": asset.mime_type,
            "media_url": self._media_url(asset.file_path),
            "width": asset.width,
            "height": asset.height,
        }

    def _serialize_character(self, character):
        if not character:
            return None
        thumbnail = self._asset_service.get_asset(character.thumbnail_asset_id) if character.thumbnail_asset_id else None
        base_asset = self._asset_service.get_asset(character.base_asset_id) if character.base_asset_id else None
        return {
            "id": character.id,
            "project_id": character.project_id,
            "name": character.name,
            "nickname": character.nickname,
            "thumbnail_asset": self._serialize_asset(thumbnail),
            "base_asset": self._serialize_asset(base_asset),
        }

    def _serialize_project(self, project):
        if not project:
            return None
        thumbnail = self._asset_service.get_asset(project.thumbnail_asset_id) if project.thumbnail_asset_id else None
        return {
            "id": project.id,
            "title": project.title,
            "summary": project.summary,
            "status": project.status,
            "thumbnail_asset": self._serialize_asset(thumbnail),
        }

    def _load_json(self, value):
        if not value:
            return {}
        try:
            parsed = json_util.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _serialize_x_schedule(self, schedule):
        if not schedule:
            return None
        return {
            "id": schedule.id,
            "feed_post_id": schedule.feed_post_id,
            "project_id": schedule.project_id,
            "created_by_user_id": schedule.created_by_user_id,
            "scheduled_for": schedule.scheduled_for.isoformat() if schedule.scheduled_for else None,
            "status": schedule.status,
            "x_post_id": schedule.x_post_id,
            "error_message": schedule.error_message,
            "metadata": self._load_json(schedule.metadata_json),
            "posted_at": schedule.posted_at.isoformat() if schedule.posted_at else None,
            "cancelled_at": schedule.cancelled_at.isoformat() if schedule.cancelled_at else None,
            "created_at": schedule.created_at.isoformat() if schedule.created_at else None,
            "updated_at": schedule.updated_at.isoformat() if schedule.updated_at else None,
        }

    def _active_x_schedule_for_post(self, post_id: int):
        return (
            FeedXSchedule.query.filter(
                FeedXSchedule.feed_post_id == post_id,
                FeedXSchedule.status == "scheduled",
            )
            .order_by(FeedXSchedule.scheduled_for.asc(), FeedXSchedule.id.asc())
            .first()
        )

    def serialize_post(self, post, *, liked_by_me: bool = False, can_manage: bool = False):
        character = self._character_service.get_character(post.character_id)
        project = self._project_service.get_project(post.project_id)
        image_asset = self._asset_service.get_asset(post.image_asset_id) if post.image_asset_id else None
        return {
            "id": post.id,
            "project_id": post.project_id,
            "character_id": post.character_id,
            "created_by_user_id": post.created_by_user_id,
            "body": post.body,
            "image_asset_id": post.image_asset_id,
            "image_asset": self._serialize_asset(image_asset),
            "status": post.status,
            "like_count": post.like_count or 0,
            "liked_by_me": liked_by_me,
            "can_manage": can_manage,
            "x_schedule": self._serialize_x_schedule(self._active_x_schedule_for_post(post.id)),
            "generation_state": self._load_json(post.generation_state_json),
            "character": self._serialize_character(character),
            "project": self._serialize_project(project),
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "updated_at": post.updated_at.isoformat() if post.updated_at else None,
        }

    def list_posts(self, *, user, can_manage_project_func, project_id=None, character_id=None, search=None, status=None, limit=50, offset=0):
        statuses = None
        if status:
            statuses = [status] if status in self.VALID_STATUSES else ["published"]
        rows = self._repo.list_posts(
            project_id=project_id,
            character_id=character_id,
            statuses=statuses,
            search=search,
            limit=limit,
            offset=offset,
        )
        visible = []
        for row in rows:
            project = self._project_service.get_project(row.project_id)
            can_manage = can_manage_project_func(user, project)
            can_edit = can_manage or row.created_by_user_id == user.id
            if row.status == "published" or can_edit:
                visible.append((row, can_edit))
        liked_ids = self._repo.liked_post_ids([row.id for row, _ in visible], user.id)
        return [
            self.serialize_post(row, liked_by_me=row.id in liked_ids, can_manage=can_manage)
            for row, can_manage in visible
        ]

    def count_posts(self, *, project_id=None, character_id=None, search=None, status=None):
        statuses = None
        if status:
            statuses = [status] if status in self.VALID_STATUSES else ["published"]
        return self._repo.count_posts(
            project_id=project_id,
            character_id=character_id,
            statuses=statuses,
            search=search,
        )

    def get_post(self, post_id: int):
        return self._repo.get_post(post_id)

    def character_post_ranking(self, *, limit: int = 10, project_id: int | None = None):
        rows = self._repo.character_post_ranking(limit=limit, project_id=project_id, published_only=True)
        return [
            {
                "rank": index + 1,
                "post_count": int(post_count or 0),
                "character": self._serialize_character(character),
                "project": self._serialize_project(project),
            }
            for index, (character, project, post_count) in enumerate(rows)
        ]

    def create_post(self, *, project_id: int, user_id: int, payload: dict):
        body = str(payload.get("body") or "").strip()
        if not body:
            raise ValueError("本文を入力してください。")
        if len(body) > 10000:
            raise ValueError("本文は10000文字以内で入力してください。")
        character_id = int(payload.get("character_id") or 0)
        character = self._character_service.get_character(character_id)
        if not character or character.project_id != project_id:
            raise ValueError("キャラクターを選択してください。")
        status = str(payload.get("status") or "draft")
        if status not in self.VALID_STATUSES:
            status = "draft"
        post = self._repo.create_post(
            {
                "project_id": project_id,
                "character_id": character_id,
                "created_by_user_id": user_id,
                "body": body,
                "image_asset_id": payload.get("image_asset_id"),
                "status": status,
            }
        )
        self.refresh_character_feed_profile(character_id)
        return post

    def generate_posts(self, *, project_id: int, user_id: int, payload: dict | None = None):
        payload = dict(payload or {})
        count = max(1, min(5, int(payload.get("count") or 1)))
        interaction_mode = self._normalize_feed_interaction_mode(
            payload.get("interaction_mode") or payload.get("mode") or "auto"
        )
        if interaction_mode == "photobook":
            return self._generate_photobook_posts(project_id=project_id, user_id=user_id, payload=payload, count=count)
        candidates = self._generate_feed_candidates(
            project_id,
            count=count,
            interaction_mode=interaction_mode,
            model=payload.get("model") or payload.get("text_ai_model"),
        )
        created = []
        for candidate in candidates[:count]:
            character_id = int(candidate.get("character_id") or 0)
            character = self._character_service.get_character(character_id)
            if not character or character.project_id != project_id:
                continue
            body = str(candidate.get("body") or "").strip()
            if not body:
                continue
            body = self._format_auto_feed_body(body, character)
            post = self._repo.create_post(
                {
                    "project_id": project_id,
                    "character_id": character.id,
                    "created_by_user_id": user_id,
                    "body": body[:10000],
                    "status": "published",
                    "generation_state_json": json_util.dumps(
                        {
                            "source": "feed_auto_generate",
                            "generated_at": datetime.utcnow().isoformat(),
                            "candidate": candidate,
                        }
                    ),
                }
            )
            post = self.generate_post_image(post.id, payload) or post
            self.refresh_character_feed_profile(character.id)
            created.append(post)
        if not created:
            raise RuntimeError("feed auto generation did not create any posts")
        return created

    def _generate_photobook_posts(self, *, project_id: int, user_id: int, payload: dict, count: int):
        characters = self._photobook_target_characters(project_id, payload, count)
        if not characters:
            raise ValueError("character is required to generate photobook Feed posts")
        locations = [
            location
            for location in self._locations.list_by_project(project_id)
            if str(getattr(location, "status", "published") or "published") == "published"
        ]
        created = []
        for character in characters[:count]:
            candidate = self._build_photobook_candidate(character, locations=locations)
            post = self._repo.create_post(
                {
                    "project_id": project_id,
                    "character_id": character.id,
                    "created_by_user_id": user_id,
                    "body": candidate["body"][:10000],
                    "status": "published",
                    "generation_state_json": json_util.dumps(
                        {
                            "source": "feed_photobook",
                            "generated_at": datetime.utcnow().isoformat(),
                            "candidate": candidate,
                        }
                    ),
                }
            )
            self.refresh_character_feed_profile(character.id)
            created.append(post)
        return created

    def _photobook_target_characters(self, project_id: int, payload: dict, count: int):
        all_characters = self._character_service.list_characters(project_id)
        try:
            character_id = int(payload.get("character_id") or 0)
        except (TypeError, ValueError):
            character_id = 0
        if character_id:
            character = self._character_service.get_character(character_id)
            if not character or character.project_id != project_id:
                raise ValueError("character is required to generate photobook Feed posts")
            return [character]
        recent_posts = self._repo.list_posts(project_id=project_id, statuses=["published"], limit=80)
        return self._select_feed_characters(all_characters, recent_posts, count=count)

    def _build_photobook_candidate(self, character, *, locations: list | None = None) -> dict:
        scene = self._photobook_scene_from_location(random.choice(locations)) if locations else random.choice(PHOTOBOOK_SCENE_PRESETS)
        outfit = self._select_photobook_outfit(character)
        composition = self._build_photobook_composition()
        display_name = self._photobook_display_name(character)
        body = f"{self._build_photobook_caption(display_name)}\n\n#AIイラスト #AIArt"
        scene_anchor = {
            "place": scene["label"],
            "place_prompt": scene["place_prompt"],
            "outfit_prompt": outfit["prompt"],
            "composition_prompt": composition,
            "outfit_source": outfit["source"],
        }
        if outfit.get("outfit_id"):
            scene_anchor["outfit_id"] = outfit["outfit_id"]
        if outfit.get("outfit_name"):
            scene_anchor["outfit_name"] = outfit["outfit_name"]
        if outfit.get("outfit_asset_id"):
            scene_anchor["outfit_asset_id"] = outfit["outfit_asset_id"]
        if scene.get("location"):
            scene_anchor.update(scene["location"])
        return {
            "character_id": character.id,
            "body": body,
            "scene_brief": f"{scene['label']}で、{display_name}が可愛く綺麗に写る写真集風の一枚。",
            "post_pattern": "写真集モード",
            "photobook": True,
            "scene_anchor": scene_anchor,
            "feed_tone": "cute_visual_only",
        }

    def _build_photobook_caption(self, display_name: str) -> str:
        return random.choice(PHOTOBOOK_CAPTION_PRESETS).format(character=display_name)

    def _build_photobook_composition(self) -> str:
        framing = random.choice(PHOTOBOOK_FRAMING_PRESETS)
        pose = random.choice(PHOTOBOOK_POSE_PRESETS)
        gaze = random.choice(PHOTOBOOK_GAZE_PRESETS)
        expression = random.choice(PHOTOBOOK_EXPRESSION_PRESETS)
        return (
            f"{framing}; pose: {pose}; gaze: {gaze}; expression: {expression}. "
            "Keep it tasteful, cute, clean, and photobook-like. Avoid repetitive over-the-shoulder glamour posing unless explicitly selected."
        )

    def _select_photobook_outfit(self, character) -> dict:
        outfits = [
            outfit
            for outfit in self._outfits.list_by_character(character.id)
            if str(getattr(outfit, "status", "active") or "active") == "active"
            and getattr(outfit, "asset_id", None)
        ]
        if outfits:
            default = next((outfit for outfit in outfits if getattr(outfit, "is_default", False)), None)
            pool = [default, *outfits] if default else outfits
            outfit = random.choice([item for item in pool if item])
            return {
                "source": "closet",
                "outfit_id": outfit.id,
                "outfit_name": outfit.name,
                "outfit_asset_id": outfit.asset_id,
                "prompt": self._photobook_outfit_prompt(outfit),
            }
        return {
            "source": "fallback",
            "prompt": random.choice(PHOTOBOOK_OUTFIT_PRESETS),
        }

    def _photobook_outfit_prompt(self, outfit) -> str:
        lines = [
            "Use the selected closet outfit as the clothing reference.",
            f"Outfit name: {getattr(outfit, 'name', '') or ''}",
        ]
        for label, value in (
            ("Description", getattr(outfit, "description", None)),
            ("Usage scene", getattr(outfit, "usage_scene", None)),
            ("Season", getattr(outfit, "season", None)),
            ("Mood", getattr(outfit, "mood", None)),
            ("Color notes", getattr(outfit, "color_notes", None)),
            ("Fixed parts", getattr(outfit, "fixed_parts", None)),
            ("Allowed changes", getattr(outfit, "allowed_changes", None)),
            ("NG rules", getattr(outfit, "ng_rules", None)),
            ("Prompt notes", getattr(outfit, "prompt_notes", None)),
        ):
            if value:
                lines.append(f"{label}: {value}")
        return " ".join(lines)

    def _photobook_display_name(self, character) -> str:
        name = str(getattr(character, "name", "") or getattr(character, "nickname", "") or "キャラクター").strip()
        return re.sub(r"(さん|ちゃん|くん|君|様|さま)$", "", name).strip() or "キャラクター"

    def _photobook_scene_from_location(self, location) -> dict:
        name = str(getattr(location, "name", "") or "施設").strip()
        location_type = str(getattr(location, "location_type", "") or "").strip()
        region = str(getattr(location, "region", "") or "").strip()
        tags = self._load_json(getattr(location, "tags_json", None))
        if not isinstance(tags, list):
            tags = []
        description = self._shorten(getattr(location, "description", None), 220)
        image_prompt = str(getattr(location, "image_prompt", "") or "").strip()
        details = []
        if region:
            details.append(f"region: {region}")
        if location_type:
            details.append(f"type: {location_type}")
        if tags:
            details.append(f"tags: {', '.join(str(tag) for tag in tags[:8])}")
        if description:
            details.append(f"description: {description}")
        place_prompt = image_prompt or f"{name}, {', '.join(details)}"
        return {
            "label": name,
            "message": f"{name}にいる{{character}}。",
            "place_prompt": place_prompt,
            "location": {
                "location_id": getattr(location, "id", None),
                "location_name": name,
                "location_type": location_type,
                "region": region,
                "tags": tags,
                "description": description,
                "image_prompt": image_prompt,
            },
        }

    def _format_auto_feed_body(self, body: str, character) -> str:
        name = str(getattr(character, "name", "") or getattr(character, "nickname", "") or "").strip()
        signature = f"\n\nー{name}" if name else ""
        return f"{body.rstrip()}{signature}\n\n#AIキャラ #ラプラスシティ"

    def update_post(self, post_id: int, payload: dict):
        normalized = {}
        current_post = self._repo.get_post(post_id)
        if not current_post:
            return None
        previous_character_id = current_post.character_id
        if "body" in payload:
            body = str(payload.get("body") or "").strip()
            if not body:
                raise ValueError("本文を入力してください。")
            if len(body) > 10000:
                raise ValueError("本文は10000文字以内で入力してください。")
            normalized["body"] = body
        if "character_id" in payload:
            character_id = int(payload.get("character_id") or 0)
            character = self._character_service.get_character(character_id)
            if not character or character.project_id != current_post.project_id:
                raise ValueError("同じワールドのキャラクターを選択してください。")
            normalized["character_id"] = character_id
        if "image_asset_id" in payload:
            normalized["image_asset_id"] = payload.get("image_asset_id") or None
        if "status" in payload:
            status = str(payload.get("status") or "draft")
            normalized["status"] = status if status in self.VALID_STATUSES else "draft"
        post = self._repo.update_post(post_id, normalized)
        if post:
            if previous_character_id != post.character_id:
                self.refresh_character_feed_profile(previous_character_id)
            self.refresh_character_feed_profile(post.character_id)
        return post

    def delete_post(self, post_id: int):
        post = self._repo.get_post(post_id)
        deleted = self._repo.delete_post(post_id)
        if post:
            self.refresh_character_feed_profile(post.character_id)
        return deleted

    def set_like(self, post_id: int, user_id: int, liked: bool):
        return self._repo.set_like(post_id, user_id, liked)

    def schedule_x_post(self, post_id: int, user_id: int, scheduled_for_value: str):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        scheduled_for = self._parse_schedule_datetime(scheduled_for_value)
        if scheduled_for <= datetime.now():
            raise ValueError("scheduled_for must be in the future")
        scheduled_for = scheduled_for.replace(minute=0, second=0, microsecond=0)
        existing = self._active_x_schedule_for_post(post_id)
        if existing:
            existing.status = "cancelled"
            existing.cancelled_at = datetime.now()
        schedule = FeedXSchedule(
            feed_post_id=post.id,
            project_id=post.project_id,
            created_by_user_id=user_id,
            scheduled_for=scheduled_for,
            status="scheduled",
            metadata_json=json_util.dumps({"source": "feed_calendar"}),
        )
        db.session.add(schedule)
        db.session.commit()
        return schedule

    def cancel_x_schedule(self, post_id: int, schedule_id: int | None = None):
        query = FeedXSchedule.query.filter(
            FeedXSchedule.feed_post_id == post_id,
            FeedXSchedule.status == "scheduled",
        )
        if schedule_id:
            query = query.filter(FeedXSchedule.id == schedule_id)
        schedule = query.order_by(FeedXSchedule.scheduled_for.asc(), FeedXSchedule.id.asc()).first()
        if not schedule:
            return None
        schedule.status = "cancelled"
        schedule.cancelled_at = datetime.now()
        db.session.commit()
        return schedule

    def publish_x_post_now(self, post_id: int, user_id: int):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        now = datetime.now()
        schedule = FeedXSchedule(
            feed_post_id=post.id,
            project_id=post.project_id,
            created_by_user_id=user_id,
            scheduled_for=now,
            status="posting",
            metadata_json=json_util.dumps({"source": "feed_manual_publish"}),
        )
        db.session.add(schedule)
        db.session.commit()
        image_asset = self._asset_service.get_asset(post.image_asset_id) if post.image_asset_id else None
        try:
            published = self._x_publishing_service.publish_feed_post(post, image_asset=image_asset)
            schedule.status = "posted"
            schedule.posted_at = datetime.now()
            schedule.x_post_id = published.get("x_post_id")
            schedule.metadata_json = json_util.dumps(
                {
                    **self._load_json(schedule.metadata_json),
                    "published": published,
                }
            )
            schedule.error_message = None
        except Exception as exc:
            schedule.status = "failed"
            schedule.error_message = str(exc)
            db.session.commit()
            raise
        db.session.commit()
        return schedule

    def list_x_schedules(self, *, project_id: int | None = None, start: str | None = None, end: str | None = None):
        start_dt = self._parse_schedule_datetime(start) if start else datetime.utcnow() - timedelta(days=1)
        end_dt = self._parse_schedule_datetime(end) if end else start_dt + timedelta(days=14)
        query = FeedXSchedule.query.filter(
            FeedXSchedule.scheduled_for >= start_dt,
            FeedXSchedule.scheduled_for < end_dt,
            FeedXSchedule.status == "scheduled",
        )
        if project_id:
            query = query.filter(FeedXSchedule.project_id == project_id)
        schedules = query.order_by(FeedXSchedule.scheduled_for.asc(), FeedXSchedule.id.asc()).all()
        return [self._serialize_x_schedule_item(schedule) for schedule in schedules]

    def publish_due_x_schedules(self, *, now: datetime | None = None, limit: int = 10):
        now = now or datetime.now()
        rows = (
            FeedXSchedule.query.filter(
                FeedXSchedule.status == "scheduled",
                FeedXSchedule.scheduled_for <= now,
            )
            .order_by(FeedXSchedule.scheduled_for.asc(), FeedXSchedule.id.asc())
            .limit(max(1, min(int(limit or 10), 50)))
            .all()
        )
        results = []
        for schedule in rows:
            post = self._repo.get_post(schedule.feed_post_id)
            if not post:
                schedule.status = "failed"
                schedule.error_message = "Feed post not found"
                db.session.commit()
                results.append(self._serialize_x_schedule(schedule))
                continue
            image_asset = self._asset_service.get_asset(post.image_asset_id) if post.image_asset_id else None
            try:
                published = self._x_publishing_service.publish_feed_post(post, image_asset=image_asset)
                schedule.status = "posted"
                schedule.posted_at = datetime.now()
                schedule.x_post_id = published.get("x_post_id")
                schedule.metadata_json = json_util.dumps(
                    {
                        **self._load_json(schedule.metadata_json),
                        "published": published,
                    }
                )
                schedule.error_message = None
            except Exception as exc:
                schedule.status = "failed"
                schedule.error_message = str(exc)
            db.session.commit()
            results.append(self._serialize_x_schedule(schedule))
        return results

    def _serialize_x_schedule_item(self, schedule):
        post = self._repo.get_post(schedule.feed_post_id)
        image_asset = self._asset_service.get_asset(post.image_asset_id) if post and post.image_asset_id else None
        data = self._serialize_x_schedule(schedule)
        data["post"] = self.serialize_post(post, can_manage=True) if post else None
        data["thumbnail_url"] = self._media_url(image_asset.file_path) if image_asset else None
        return data

    def _parse_schedule_datetime(self, value):
        text = str(value or "").strip()
        if not text:
            raise ValueError("scheduled_for is required")
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("scheduled_for must be ISO datetime") from exc
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed

    def import_from_url(self, project_id: int, url: str):
        normalized_url = self._normalize_import_url(url)
        html_text = self._fetch_url_html(normalized_url)
        metadata = self._extract_url_metadata(html_text)
        if self._is_x_url(normalized_url):
            metadata = {**metadata, **self._extract_x_metadata(html_text)}
        body = self._clean_imported_body(
            metadata.get("og:description")
            or metadata.get("twitter:description")
            or metadata.get("description")
            or metadata.get("x:full_text")
            or metadata.get("og:title")
            or metadata.get("twitter:title")
            or ""
        )
        image_url = (
            metadata.get("og:image")
            or metadata.get("twitter:image")
            or metadata.get("twitter:image:src")
            or metadata.get("x:image")
        )
        asset = self._download_import_image(project_id, image_url, source_url=normalized_url) if image_url else None
        if not body and not asset:
            raise ValueError("URLから本文または画像を取得できませんでした。")
        return {
            "source_url": normalized_url,
            "body": body,
            "image_asset": self._serialize_asset(asset),
            "metadata": {
                "title": metadata.get("og:title") or metadata.get("twitter:title") or "",
                "image_url": image_url,
            },
        }

    def _normalize_import_url(self, url: str):
        value = str(url or "").strip()
        if not value:
            raise ValueError("URLを入力してください。")
        match = re.search(r"https?://[^\s]+", value)
        value = match.group(0).rstrip("）。),]") if match else value
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("httpまたはhttpsのURLを入力してください。")
        return value

    def _fetch_url_html(self, url: str):
        response = self._safe_get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=15,
        )
        if response.status_code >= 400:
            raise ValueError(f"URLの取得に失敗しました。HTTP {response.status_code}")
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise ValueError("HTMLページではないため取り込めません。")
        return response.text

    def _extract_url_metadata(self, html_text: str):
        parser = _MetaTagParser()
        parser.feed(html_text or "")
        return parser.meta

    def _is_x_url(self, url: str):
        hostname = (urlparse(url).hostname or "").lower()
        return hostname in {"x.com", "twitter.com", "www.x.com", "www.twitter.com", "mobile.twitter.com"}

    def _decode_json_string_fragment(self, value: str):
        try:
            return json_util.loads(f'"{value}"')
        except Exception:
            try:
                return bytes(value, "utf-8").decode("unicode_escape")
            except Exception:
                return value

    def _extract_x_metadata(self, html_text: str):
        metadata = {}
        text = html_text or ""
        full_text_match = re.search(r'"full_text"\s*:\s*"((?:\\.|[^"\\])*)"', text)
        if full_text_match:
            metadata["x:full_text"] = self._decode_json_string_fragment(full_text_match.group(1))
        image_match = re.search(r'"media_url_https"\s*:\s*"(https://pbs\.twimg\.com/media/[^"\\]+)"', text)
        if not image_match:
            image_match = re.search(r'(https://pbs\.twimg\.com/media/[^"\\<> ]+)', text)
        if image_match:
            metadata["x:image"] = self._decode_json_string_fragment(image_match.group(1))
        return metadata

    def _clean_imported_body(self, text: str):
        value = unescape(str(text or "")).strip()
        if not value:
            return ""
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        value = re.sub(r"[ \t\f\v]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        value = re.sub(r"^.+?\s+on\s+X:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^.+?\s+on\s+Twitter:\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s+https?://t\.co/\S+", "", value)
        value = re.sub(r"\s+pic\.twitter\.com/\S+", "", value, flags=re.IGNORECASE)
        value = value.strip(" \n\r\t\"'")
        return value[:10000]

    def _download_import_image(self, project_id: int, image_url: str | None, *, source_url: str):
        if not image_url:
            return None
        parsed = urlparse(image_url)
        if parsed.scheme not in {"http", "https"}:
            return None
        response = self._safe_get(
            image_url,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "image/*,*/*;q=0.8"},
            timeout=20,
            stream=True,
        )
        if response.status_code >= 400:
            return None
        mime_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
        if not mime_type.startswith("image/"):
            return None
        max_bytes = int(current_app.config.get("FEED_IMPORT_IMAGE_MAX_BYTES", 10 * 1024 * 1024))
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > max_bytes:
            raise ValueError("image is too large")
        raw_bytes = response.content
        if not raw_bytes:
            return None
        if len(raw_bytes) > max_bytes:
            raise ValueError("image is too large")
        extension = mimetypes.guess_extension(mime_type) or ".jpg"
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "assets", "feed_import")
        os.makedirs(output_dir, exist_ok=True)
        file_name = f"feed_import_{uuid.uuid4().hex[:12]}{extension}"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return self._asset_service.create_asset(
            project_id,
            {
                "asset_type": "feed_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": mime_type,
                "file_size": len(raw_bytes),
                "checksum": hashlib.sha256(raw_bytes).hexdigest(),
                "metadata_json": json_util.dumps(
                    {
                        "source": "feed_url_import",
                        "source_url": source_url,
                        "image_url": image_url,
                    }
                ),
            },
        )

    def _safe_get(self, url: str, *, headers: dict, timeout: int, stream: bool = False):
        current_url = url
        for _ in range(4):
            self._validate_public_http_url(current_url)
            response = requests.get(
                current_url,
                headers=headers,
                timeout=timeout,
                stream=stream,
                allow_redirects=False,
            )
            if response.is_redirect or response.is_permanent_redirect:
                location = response.headers.get("location")
                if not location:
                    return response
                current_url = urljoin(current_url, location)
                continue
            return response
        raise ValueError("too many redirects")

    def _validate_public_http_url(self, url: str):
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("httpまたはhttpsのURLを入力してください。")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            addresses = socket.getaddrinfo(parsed.hostname, port)
        except socket.gaierror as exc:
            raise ValueError("URLの名前解決に失敗しました。") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise ValueError("このURLは取り込めません。")

    def upload_post_image(self, post_id: int, upload_file):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        asset = self._asset_service.create_asset(
            post.project_id,
            {
                "asset_type": "feed_image",
                "upload_file": upload_file,
            },
        )
        post = self._repo.update_post(post.id, {"image_asset_id": asset.id})
        return post

    def generate_post_image(self, post_id: int, payload: dict | None = None):
        post = self._repo.get_post(post_id)
        if not post:
            return None
        payload = dict(payload or {})
        character = self._character_service.get_character(post.character_id)
        project = self._project_service.get_project(post.project_id)
        world = self._world_service.get_world(post.project_id)
        generation_state = self._load_json(post.generation_state_json)
        prompt = self._build_feed_image_prompt(post, character, project, world, payload)
        reference_paths = []
        reference_ids = []
        if character and character.base_asset_id:
            base_asset = self._asset_service.get_asset(character.base_asset_id)
            if base_asset and os.path.exists(base_asset.file_path):
                reference_paths.append(base_asset.file_path)
                reference_ids.append(base_asset.id)
        candidate = generation_state.get("candidate") if isinstance(generation_state.get("candidate"), dict) else {}
        scene_anchor = candidate.get("scene_anchor") if isinstance(candidate.get("scene_anchor"), dict) else {}
        for raw_asset_id in (scene_anchor.get("outfit_asset_id"), candidate.get("outfit_asset_id")):
            try:
                outfit_asset_id = int(raw_asset_id or 0)
            except (TypeError, ValueError):
                outfit_asset_id = 0
            if outfit_asset_id and outfit_asset_id not in reference_ids:
                outfit_asset = self._asset_service.get_asset(outfit_asset_id)
                if outfit_asset and os.path.exists(outfit_asset.file_path):
                    reference_paths.append(outfit_asset.file_path)
                    reference_ids.append(outfit_asset.id)
        try:
            co_character_id = int(candidate.get("co_character_id") or 0)
        except (TypeError, ValueError):
            co_character_id = 0
        if co_character_id and co_character_id != int(getattr(character, "id", 0) or 0):
            co_character = self._character_service.get_character(co_character_id)
            if co_character and getattr(co_character, "base_asset_id", None):
                co_asset = self._asset_service.get_asset(co_character.base_asset_id)
                if co_asset and os.path.exists(co_asset.file_path) and co_asset.id not in reference_ids:
                    reference_paths.append(co_asset.file_path)
                    reference_ids.append(co_asset.id)
        result = self._image_ai_client.generate_image(
            prompt,
            size=payload.get("size") or "1536x1024",
            quality=payload.get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            model=payload.get("image_ai_model") or payload.get("model"),
            provider=payload.get("provider") or payload.get("image_ai_provider"),
            output_format="png",
            background="opaque",
            input_image_paths=reference_paths,
            input_fidelity="high" if reference_paths else None,
        )
        image_base64 = result.get("image_base64")
        if not image_base64:
            raise RuntimeError("image generation response did not include image_base64")
        file_name, file_path, file_size = self._store_generated_feed_image(post.project_id, post.id, image_base64)
        asset = self._asset_service.create_asset(
            post.project_id,
            {
                "asset_type": "feed_image",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps(
                    {
                        "source": "feed_post_image",
                        "feed_post_id": post.id,
                        "prompt": prompt,
                        "revised_prompt": result.get("revised_prompt"),
                        "reference_asset_ids": reference_ids,
                        "model": result.get("model"),
                    }
                ),
            },
        )
        generation_state.update(
            {
                "image_prompt": prompt,
                "revised_prompt": result.get("revised_prompt"),
                "generated_at": datetime.utcnow().isoformat(),
                "reference_asset_ids": reference_ids,
            }
        )
        post = self._repo.update_post(
            post.id,
            {
                "image_asset_id": asset.id,
                "generation_state_json": json_util.dumps(generation_state),
            },
        )
        return post

    def _generate_feed_candidates(self, project_id: int, *, count: int, interaction_mode: str = "auto", model: str | None = None):
        project = self._project_service.get_project(project_id)
        world = self._world_service.get_world(project_id)
        all_characters = self._character_service.list_characters(project_id)
        locations = self._locations.list_by_project(project_id)
        recent_posts = self._repo.list_posts(project_id=project_id, statuses=["published"], limit=80)
        characters = self._select_feed_characters(all_characters, recent_posts, count=count)
        if not characters:
            raise ValueError("character is required to generate Feed posts")
        selected_ids = [character.id for character in characters]
        recent_scene_anchors = self._recent_feed_scene_anchors(recent_posts)
        post_plans = self._build_feed_post_plans(
            characters,
            all_characters,
            interaction_mode=interaction_mode,
            recent_scene_anchors=recent_scene_anchors,
            locations=locations,
        )
        prompt = f"""
Return only JSON.
Create {count} public Feed posts for a Japanese character world app.
Each item is a short X-like character/world post, not a polite diary, not a news article, and not a chat reply.

Required shape:
{{"items":[{{"character_id": 1, "scene_brief": "...", "body": "...", "post_pattern": "..."}}]}}

Rules:
- Japanese only.
- Use only provided character IDs.
- Create exactly one item for each target character ID: {json_util.dumps(selected_ids)}.
- Do not use any character ID outside target character IDs.
- Keep each body 35-130 Japanese characters.
- Match the selected character's personality and speech style.
- Follow the assigned post_pattern for each target character.
- The assigned target character must be the speaker or main subject of the post.
- If a post plan has co_character, include that co_character as the interaction partner.
- If another character appears, the target character must still appear and remain the main subject, and the co_character should be the only major partner.
- If a post plan has no co_character, do not mention any other named character. Use staff, customer, witness, or passerby instead.
- For duo posts, make the relationship readable in one simple exchange or incident.
- Follow each post plan's scene_anchor, feed_tone, comedy_style, romcom_intensity, and romcom_device.
- Use scene_anchor as the DB location source, but write like a casual Feed post, not an article.
- First create scene_brief: 1-2 plain Japanese sentences describing the exact visual incident for image generation.
- scene_brief must include who, where/visible place clue, what object/action/mishap happens, and the target character's visible emotion or reaction.
- Then write body as a casual X-like Feed post derived from that same scene_brief.
- Do not let body introduce a different location, character, object, or incident from scene_brief.
- The post only needs one imageable beat: one character, one action or mishap, one emotion or punchline.
- You may omit the facility name if the prop/action makes the place clear.
- Avoid reusing recent scene anchors, but do not over-explain the setting.
- Do not make every post romantic. If romcom_intensity is none or low, keep romance absent or only a tiny hint.
- If romcom_intensity is medium or high, use a safe, concrete love-comedy or embarrassment beat that can become a strong image.
- Teasing or fanservice-like mishaps must stay tasteful and non-explicit: no nudity, no exposed intimate body parts, no sexual description, no coercion.
- Make the post feel like X: casual, punchy, reactive, and easy to reply to.
- Prefer direct speech, first-person reactions, quick confessions, sightings, or one-line incident reports.
- The funny part should be easy to picture without hidden lore.
- Do not mention that AI generated the post.
- Do not include a signature line, character name footer, hashtags, or social tags. The app will append them.
- Avoid duplicating recent posts.
- Avoid abstract poetic summaries and unclear invented nouns.

Style examples:
- もー！何よ、これ。みんなに誕生日お祝いでクラッカー鳴らしてもらったんだけど、全部私の身体に絡まっちゃって……
- 技術屋はダンスが苦手？はっはっは！それは偏見だ。わたしはブレイクダンスが趣味なんだ
- ミウがライブのリハーサルで歌おうと思ったら、マイクのケーブルが脚に絡まって尻もち着いちゃった。見てないよね？

Project: {getattr(project, "title", "") or ""}
Project summary: {getattr(project, "summary", "") or ""}
World tone: {getattr(world, "tone", "") if world else ""}
World overview: {getattr(world, "overview", "") if world else ""}
Characters: {json_util.dumps([self._feed_character_context(character) for character in characters])}
Available co-characters: {json_util.dumps([self._feed_character_context(character) for character in all_characters[:30]])}
Post plans: {json_util.dumps(post_plans)}
Recent posts: {json_util.dumps([{"character_id": post.character_id, "body": post.body} for post in recent_posts[:12]])}
Recent scene anchors to avoid: {json_util.dumps(recent_scene_anchors[:12])}
""".strip()
        result = self._text_ai_client.generate_text(
            prompt,
            model=model,
            response_format={"type": "json_object"},
            temperature=0.85,
            max_tokens=1600,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        items = parsed.get("items") if isinstance(parsed, dict) else []
        if isinstance(items, list) and items:
            return self._normalize_feed_candidate_characters(items, characters, post_plans, all_characters=all_characters)
        raise RuntimeError("Feed自動生成に失敗しました。固定フォールバックは使わず、再生成してください。")

    def _normalize_feed_interaction_mode(self, value):
        mode = str(value or "auto").strip().lower()
        if mode in {"solo", "single", "one", "1", "single_character"}:
            return "solo"
        if mode in {"duo", "pair", "two", "2", "two_character"}:
            return "duo"
        if mode in {"photobook", "photo_book", "photo", "album", "gravure", "portfolio"}:
            return "photobook"
        return "auto"

    def _feed_tone_instruction(self, tone: str) -> str:
        return {
            "incident_report": "Make it a quick public incident report with a clear cause, reaction, and punchline.",
            "deadpan_notice": "Write like a dry notice or official-sounding post where the absurdity is in the calm wording.",
            "chaotic_live_report": "Make it feel like someone is reporting from the scene while things are still going wrong.",
            "character_confession": "Make the speaker accidentally reveal a feeling or weakness while trying to sound normal.",
            "facility_trouble": "Center the post on a facility, device, sign, menu, cable, rope, door, light, or rule causing trouble.",
            "food_or_prop_comedy": "Make a concrete food item or prop drive the joke.",
            "romcom_mishap": "Use a safe love-comedy physical mishap with embarrassment, timing, and witnesses.",
        }.get(tone, "Make it a punchy Feed post with one clear situation and punchline.")

    def _feed_comedy_style_instruction(self, style: str) -> str:
        return {
            "deadpan": "Keep the wording calm and let the situation be absurd.",
            "overreaction": "Make bystanders or the speaker overreact to a small event.",
            "misunderstanding": "Build the joke around a harmless misunderstanding.",
            "witness_report": "Use a witness/sighting format with one vivid detail.",
            "self_own": "Let the target character accidentally embarrass themselves.",
            "bureaucratic_absurdity": "Use rules, rankings, warnings, forms, or official wording as the joke.",
            "physical_comedy": "Use motion, stumbling, tangled objects, dropped props, or bad timing as the joke.",
        }.get(style, "Use a light comedic angle.")

    def _feed_romcom_intensity_instruction(self, intensity: str) -> str:
        return {
            "none": "No romantic beat is required. Keep it as comedy, incident, facility, or character behavior.",
            "low": "Use only a tiny romantic hint if it fits; do not force it.",
            "medium": "If it fits, make romantic tension readable through one concrete reaction invented from the facility and character context.",
            "high": "Make the love-comedy energy obvious, but invent the mechanism from the facility and keep it safe and non-explicit.",
        }.get(intensity, "Use romantic tension only if it fits the plan.")

    def _feed_romcom_device_instruction(self, device: str) -> str:
        return {
            "none": "No special romantic-comedy device.",
            "near_fall": "Use a near fall or stumble. The joke can be the recovery, the failed excuse, or a prop getting kicked away; close distance is optional, not required.",
            "rope_or_cable_tangle": "Use a rope, ribbon, cable, strap, or lanyard catching on clothing or props and causing awkward timing. Focus on the tangle and frantic fixing, not faces getting close.",
            "wardrobe_mishap": "Use a tasteful wardrobe trouble moment: snagged hem, slipping jacket, twisted ribbon, loose accessory, or hurried cover-up gesture. No nudity or explicit exposure.",
            "flustered_coverup": "Use a rushed cover-up, badly timed denial, or over-formal explanation after a harmless mishap.",
            "jealous_object": "Use jealousy displaced onto an object, menu, score, seat, gift, or device rather than a crowd reaction.",
            "secret_kindness": "Use a small helpful act that the character tries to hide, such as fixing something, saving a seat, or quietly returning an item.",
            "failed_cool_pose": "Use the character trying to look composed or cool, then being undercut by a prop, sign, device, or timing.",
            "overheard_line": "Use one overheard line that sounds romantic out of context, then reveal a silly literal cause.",
        }.get(device, "Use a safe, concrete love-comedy device only if the plan calls for it.")

    def _feed_scene_anchor(self, romcom_device: str, feed_tone: str, locations: list | None = None) -> dict:
        location = random.choice(locations) if locations else None
        return {
            "place": getattr(location, "name", None) or "プロジェクト内のどこかの施設",
            "location_id": getattr(location, "id", None),
            "location_name": getattr(location, "name", None),
            "location_type": getattr(location, "location_type", None),
            "region": getattr(location, "region", None),
            "tags": self._load_json(getattr(location, "tags_json", None)) if location else [],
            "description": self._shorten(getattr(location, "description", None), 180),
            "scene_task": "Use this DB location as the source. Choose a concrete prop, service, fixture, menu item, machine, seat, sign, decoration, staff action, or event that naturally belongs to this location. Do not use a fixed generic template if it does not fit the location.",
            "event_task": "Create a specific small incident from the location's name, type, tags, and description. The post must explain the concrete object and action in plain words.",
            "romcom_device": romcom_device,
            "feed_tone": feed_tone,
        }

    def _recent_feed_scene_anchors(self, recent_posts) -> list[dict]:
        anchors = []
        for post in recent_posts[:24]:
            state = self._load_json(getattr(post, "generation_state_json", None))
            candidate = state.get("candidate") if isinstance(state.get("candidate"), dict) else {}
            anchor = candidate.get("scene_anchor") if isinstance(candidate.get("scene_anchor"), dict) else {}
            if anchor:
                anchors.append(
                    {
                        "place": anchor.get("place"),
                        "object": anchor.get("object"),
                        "action": anchor.get("action"),
                        "problem": anchor.get("problem"),
                    }
                )
        return anchors

    def _feed_scene_anchor_key(self, anchor: dict | None) -> str:
        anchor = anchor or {}
        return f"{anchor.get('place') or ''}|{anchor.get('object') or ''}".strip("|")

    def _shorten(self, value, limit: int) -> str:
        text = str(value or "").strip().replace("\r\n", "\n")
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def _build_feed_post_plans(
        self,
        characters,
        all_characters=None,
        interaction_mode: str = "auto",
        recent_scene_anchors: list[dict] | None = None,
        locations: list | None = None,
    ):
        mode = self._normalize_feed_interaction_mode(interaction_mode)
        solo_patterns = FEED_POST_PATTERNS
        if mode == "solo":
            duo_pattern_names = {pattern["name"] for pattern in FEED_DUO_POST_PATTERNS}
            solo_patterns = [pattern for pattern in FEED_POST_PATTERNS if pattern["name"] not in duo_pattern_names]
        patterns = random.sample(solo_patterns, k=min(len(characters), len(solo_patterns)))
        if len(patterns) < len(characters):
            patterns.extend(random.choice(solo_patterns) for _ in range(len(characters) - len(patterns)))
        all_characters = [character for character in (all_characters or characters) if getattr(character, "id", None)]
        recent_scene_keys = {
            self._feed_scene_anchor_key(anchor)
            for anchor in (recent_scene_anchors or [])
            if self._feed_scene_anchor_key(anchor)
        }
        used_scene_keys = set()
        plans = []
        for character, pattern in zip(characters, patterns):
            use_duo = mode == "duo" or (mode == "auto" and len(all_characters) >= 2 and random.random() < 0.45)
            use_duo = use_duo and len(all_characters) >= 2
            co_character = None
            if use_duo:
                partners = [candidate for candidate in all_characters if int(candidate.id) != int(character.id)]
                co_character = random.choice(partners) if partners else None
                pattern = random.choice(FEED_DUO_POST_PATTERNS)
            feed_tone = random.choice(
                [
                    "incident_report",
                    "deadpan_notice",
                    "chaotic_live_report",
                    "character_confession",
                    "facility_trouble",
                    "food_or_prop_comedy",
                    "romcom_mishap",
                ]
            )
            comedy_style = random.choice(
                [
                    "deadpan",
                    "overreaction",
                    "misunderstanding",
                    "witness_report",
                    "self_own",
                    "bureaucratic_absurdity",
                    "physical_comedy",
                ]
            )
            romcom_intensity = random.choice(["none", "none", "low", "medium", "high"])
            if feed_tone == "romcom_mishap" or use_duo:
                romcom_intensity = random.choice(["low", "medium", "medium", "high"])
            romcom_device = "none"
            if romcom_intensity in {"medium", "high"}:
                romcom_device = random.choice(
                    [
                        "near_fall",
                        "rope_or_cable_tangle",
                        "wardrobe_mishap",
                        "flustered_coverup",
                        "jealous_object",
                        "secret_kindness",
                        "failed_cool_pose",
                        "overheard_line",
                    ]
                )
            scene_anchor = {}
            for _attempt in range(80):
                candidate_anchor = self._feed_scene_anchor(romcom_device, feed_tone, locations=locations)
                candidate_key = self._feed_scene_anchor_key(candidate_anchor)
                scene_anchor = candidate_anchor
                if candidate_key and candidate_key not in recent_scene_keys and candidate_key not in used_scene_keys:
                    break
            scene_key = self._feed_scene_anchor_key(scene_anchor)
            if scene_key:
                used_scene_keys.add(scene_key)
            plans.append(
                {
                    "character_id": character.id,
                    "character_name": getattr(character, "name", "") or "",
                    "post_pattern": pattern["name"],
                    "pattern_instruction": pattern["instruction"],
                    "scene_anchor": scene_anchor,
                    "feed_tone": feed_tone,
                    "feed_tone_instruction": self._feed_tone_instruction(feed_tone),
                    "comedy_style": comedy_style,
                    "comedy_style_instruction": self._feed_comedy_style_instruction(comedy_style),
                    "romcom_intensity": romcom_intensity,
                    "romcom_intensity_instruction": self._feed_romcom_intensity_instruction(romcom_intensity),
                    "romcom_device": romcom_device,
                    "romcom_device_instruction": self._feed_romcom_device_instruction(romcom_device),
                    "co_character_id": getattr(co_character, "id", None) if co_character else None,
                    "co_character_name": getattr(co_character, "name", None) if co_character else None,
                    "co_character": self._feed_character_context(co_character) if co_character else None,
                }
            )
        return plans

    def _select_feed_characters(self, characters, recent_posts, *, count: int):
        available = [character for character in characters if getattr(character, "id", None)]
        if not available:
            return []
        recent_counts = Counter(int(post.character_id) for post in recent_posts[:20] if getattr(post, "character_id", None))
        total_counts = Counter(int(post.character_id) for post in recent_posts if getattr(post, "character_id", None))
        latest_index = {}
        for index, post in enumerate(recent_posts):
            character_id = int(getattr(post, "character_id", 0) or 0)
            latest_index.setdefault(character_id, index)
        jitter = {character.id: random.random() for character in available}
        ranked = sorted(
            available,
            key=lambda character: (
                recent_counts.get(character.id, 0),
                total_counts.get(character.id, 0),
                latest_index.get(character.id, -1) >= 0,
                -latest_index.get(character.id, -1),
                jitter.get(character.id, 0),
            ),
        )
        return ranked[: max(1, min(int(count or 1), len(ranked)))]

    def _normalize_feed_candidate_characters(self, items, target_characters, post_plans=None, all_characters=None):
        target_ids = [int(character.id) for character in target_characters]
        target_id_set = set(target_ids)
        target_by_id = {int(character.id): character for character in target_characters}
        plans_by_character_id = {
            int(plan.get("character_id")): plan
            for plan in (post_plans or [])
            if plan.get("character_id")
        }
        normalized = []
        used_ids = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                character_id = int(item.get("character_id") or 0)
            except (TypeError, ValueError):
                character_id = 0
            if character_id not in target_id_set or character_id in used_ids:
                remaining = [target_id for target_id in target_ids if target_id not in used_ids]
                if not remaining:
                    continue
                character_id = remaining[0]
            body = str(item.get("body") or "").strip()
            if not body:
                continue
            plan = plans_by_character_id.get(character_id)
            if self._body_uses_wrong_primary_character(
                body,
                target_by_id.get(character_id),
                all_characters or target_characters,
                plan,
            ):
                continue
            if self._body_has_unclear_feed_phrase(body):
                continue
            candidate = dict(item)
            candidate["character_id"] = character_id
            candidate["body"] = body
            candidate["scene_brief"] = self._normalize_feed_scene_brief(
                candidate.get("scene_brief"),
                body,
                target_by_id.get(character_id),
                plan,
            )
            if plan:
                candidate["post_pattern"] = plan.get("post_pattern")
                candidate["pattern_instruction"] = plan.get("pattern_instruction")
                candidate["scene_anchor"] = plan.get("scene_anchor")
                candidate["co_character_id"] = plan.get("co_character_id")
                candidate["co_character_name"] = plan.get("co_character_name")
                candidate["co_character"] = plan.get("co_character")
                candidate["feed_tone"] = plan.get("feed_tone")
                candidate["feed_tone_instruction"] = plan.get("feed_tone_instruction")
                candidate["comedy_style"] = plan.get("comedy_style")
                candidate["comedy_style_instruction"] = plan.get("comedy_style_instruction")
                candidate["romcom_intensity"] = plan.get("romcom_intensity")
                candidate["romcom_intensity_instruction"] = plan.get("romcom_intensity_instruction")
                candidate["romcom_device"] = plan.get("romcom_device")
                candidate["romcom_device_instruction"] = plan.get("romcom_device_instruction")
            normalized.append(candidate)
            used_ids.add(character_id)
        if len(normalized) < len(target_ids):
            missing_ids = [target_id for target_id in target_ids if target_id not in used_ids]
            raise RuntimeError(
                "Feed自動生成に失敗しました。"
                f"AI候補の一部が検証で除外されました: missing_character_ids={missing_ids}"
            )
        return normalized

    def _body_uses_wrong_primary_character(self, body: str, target_character, target_characters, plan=None) -> bool:
        if not target_character:
            return False
        target_name = str(getattr(target_character, "name", "") or "").strip()
        target_nickname = str(getattr(target_character, "nickname", "") or "").strip()
        target_tokens = [token for token in (target_name, target_nickname) if token]
        allowed_partner_tokens = set(target_tokens)
        plan = plan or {}
        if plan.get("co_character_name"):
            allowed_partner_tokens.add(str(plan.get("co_character_name")).strip())
        co_character = plan.get("co_character") if isinstance(plan.get("co_character"), dict) else {}
        for token in (co_character.get("name"), co_character.get("nickname")):
            if token:
                allowed_partner_tokens.add(str(token).strip())
        other_tokens = []
        for character in target_characters:
            if int(getattr(character, "id", 0) or 0) == int(getattr(target_character, "id", 0) or 0):
                continue
            other_tokens.extend(
                token
                for token in (
                    str(getattr(character, "name", "") or "").strip(),
                    str(getattr(character, "nickname", "") or "").strip(),
                )
                if token and len(token) >= 2
            )
        other_tokens = [token for token in other_tokens if token not in allowed_partner_tokens]
        return any(token in body for token in other_tokens)

    def _body_has_unclear_feed_phrase(self, body: str) -> bool:
        unclear_fragments = (
            "余裕ある待機席",
            "余裕のある待機席",
            "恋の事故みたい",
            "感情の椅子",
            "本音の装置",
            "照れの端末",
        )
        return any(fragment in body for fragment in unclear_fragments)

    def _normalize_feed_scene_brief(self, value, body: str, character=None, plan=None) -> str:
        brief = re.sub(r"\s+", " ", str(value or "").strip())
        if len(brief) > 220:
            brief = brief[:220].rstrip()
        if brief and len(brief) >= 20:
            return brief
        plan = plan or {}
        character_name = getattr(character, "name", "") or plan.get("character_name") or "target character"
        scene_anchor = plan.get("scene_anchor") if isinstance(plan.get("scene_anchor"), dict) else {}
        place = scene_anchor.get("place") or scene_anchor.get("location_name") or "the selected world location"
        co_character = plan.get("co_character_name")
        partner = f" with {co_character}" if co_character else ""
        return (
            f"{character_name}{partner} at {place}: depict the concrete incident from this Feed body as one visible moment. "
            f"Feed body: {body[:160]}"
        )

    def _fallback_feed_candidates(self, characters, count: int, *, post_plans=None):
        raise RuntimeError("Feed自動生成の固定フォールバックは無効です。再生成してください。")
        plans_by_character_id = {
            int(plan.get("character_id")): plan
            for plan in (post_plans or [])
            if plan.get("character_id")
        }
        items = []
        for index in range(count):
            character = characters[index % len(characters)]
            name = getattr(character, "name", "") or "私"
            plan = plans_by_character_id.get(int(character.id), {})
            pattern_name = plan.get("post_pattern") or "速報・事件型"
            co_character_name = str(plan.get("co_character_name") or "").strip()
            if co_character_name:
                body = f"{name}と{co_character_name}まわりで小事件発生。ラプラスシティの通路で二人が同じ端末をのぞき込んだ瞬間、警告灯だけが先に赤くなりました。原因は設定ミスらしいですが、目撃者いわく「先に照れたのは端末」。"
            else:
                body = f"【{pattern_name}】{name}まわりで小事件発生。ラプラスシティの通路で妙な注目を集めた結果、本人だけが平静を装っています。詳細は不明ですが、目撃者いわく「たぶんいつものやつ」。"
            items.append(
                {
                    "character_id": character.id,
                    "scene_brief": self._normalize_feed_scene_brief(None, body, character, plan),
                    "post_pattern": pattern_name,
                    "pattern_instruction": plan.get("pattern_instruction"),
                    "scene_anchor": plan.get("scene_anchor"),
                    "co_character_id": plan.get("co_character_id"),
                    "co_character_name": co_character_name or None,
                    "co_character": plan.get("co_character"),
                    "feed_tone": plan.get("feed_tone"),
                    "feed_tone_instruction": plan.get("feed_tone_instruction"),
                    "comedy_style": plan.get("comedy_style"),
                    "comedy_style_instruction": plan.get("comedy_style_instruction"),
                    "romcom_intensity": plan.get("romcom_intensity"),
                    "romcom_intensity_instruction": plan.get("romcom_intensity_instruction"),
                    "romcom_device": plan.get("romcom_device"),
                    "romcom_device_instruction": plan.get("romcom_device_instruction"),
                    "body": body,
                }
            )
        return items

    def _feed_character_context(self, character) -> dict:
        if not character:
            return {}
        return {
            "id": character.id,
            "name": character.name,
            "nickname": character.nickname,
            "character_summary": getattr(character, "character_summary", None),
            "personality": character.personality,
            "speech_style": character.speech_style,
            "appearance": character.appearance_summary,
            "art_style": getattr(character, "art_style", None),
        }

    def _build_feed_image_prompt(self, post, character, project, world, payload: dict):
        override = str(payload.get("prompt") or "").strip()
        if override:
            return override
        generation_state = self._load_json(getattr(post, "generation_state_json", None))
        candidate = generation_state.get("candidate") if isinstance(generation_state.get("candidate"), dict) else {}
        post_pattern = str(candidate.get("post_pattern") or generation_state.get("post_pattern") or "").strip()
        pattern_instruction = str(candidate.get("pattern_instruction") or "").strip()
        scene_anchor = candidate.get("scene_anchor") if isinstance(candidate.get("scene_anchor"), dict) else {}
        feed_tone = str(candidate.get("feed_tone") or "").strip()
        comedy_style = str(candidate.get("comedy_style") or "").strip()
        romcom_intensity = str(candidate.get("romcom_intensity") or "").strip()
        romcom_device = str(candidate.get("romcom_device") or "").strip()
        scene_brief = str(candidate.get("scene_brief") or "").strip()
        co_character = candidate.get("co_character") if isinstance(candidate.get("co_character"), dict) else {}
        co_character_name = str(candidate.get("co_character_name") or co_character.get("name") or "").strip()
        if candidate.get("photobook") or generation_state.get("source") == "feed_photobook":
            return self._build_photobook_image_prompt(post, character, project, world, candidate)
        lines = [
            "Create a high-impact Feed image for a character conversation app.",
            "Use the reference images as the primary source of character identity and art style.",
            "If multiple reference images are provided, the first reference is the target character and the second reference is the co-character.",
            "Keep the same face, hair, outfit design logic, coloring, rendering quality, material detail, and mood for every referenced character.",
            "All characters in the image must share one unified high-end 3D, semi-realistic, cinematic game-CG style. Do not render the co-character as flat illustration, chibi, manga, sketch, or lower-detail anime art.",
            "No speech bubbles, no dialogue text, no subtitles, no UI overlay, no logo, no watermark.",
            "Readable in-world text is allowed when it naturally belongs to the scene: blackboard notes, classroom boards, signs, posters, notice boards, terminal screens, menu boards, labels, maps, presentation slides, or documents. Keep it short, legible, and relevant to the Feed post.",
            "Show the target character as the main subject. Do not show the player.",
            "Do not make a simple standing portrait, idle pose, catalog pose, or generic promotional still.",
            "The image must depict the incident, joke, rumor, failure, poll, strange notice, romantic mishap, or facility trouble described by the Feed post.",
            "Make it feel like a dramatic social-media incident photo or visual novel event CG: caught-in-the-act composition, expressive reaction, visible cause of the problem, and a clear environment.",
            "The character should be doing something specific: reacting, pointing, stumbling, holding an object, inspecting a broken device, confronting a sign, reaching toward food, shielding themselves from chaos, or being caught mid-action.",
            "Use dynamic camera language where appropriate: dutch angle, close foreground object, motion blur, over-the-shoulder framing, dramatic lighting, cluttered evidence, or a comedic reveal in the background.",
            "The viewer should understand the post's situation from the image alone, even without reading the text.",
        ]
        if scene_brief:
            lines.append(f"Primary visual scene brief: {scene_brief}")
            lines.append("Treat the primary visual scene brief as the main source of truth for composition, action, props, and emotion.")
        lines.append(f"Feed post body: {post.body}")
        if post_pattern:
            lines.append(f"Feed post pattern: {post_pattern}")
        if pattern_instruction:
            lines.append(f"Pattern instruction: {pattern_instruction}")
        if scene_anchor:
            lines.append(f"Scene anchor: {json_util.dumps(scene_anchor)}")
            lines.append("Depict this DB location clearly. Derive the visible prop/action from the location name, type, tags, and description; do not use a generic repeated prop/action template if it does not fit this location.")
        if feed_tone:
            lines.append(f"Feed tone: {feed_tone}")
            lines.append(f"Feed tone instruction: {candidate.get('feed_tone_instruction') or ''}")
        if comedy_style:
            lines.append(f"Comedy style: {comedy_style}")
            lines.append(f"Comedy style instruction: {candidate.get('comedy_style_instruction') or ''}")
        if romcom_intensity:
            lines.append(f"Romcom intensity: {romcom_intensity}")
            lines.append(f"Romcom intensity instruction: {candidate.get('romcom_intensity_instruction') or ''}")
        if romcom_device and romcom_device != "none":
            lines.append(f"Romcom device: {romcom_device}")
            lines.append(f"Romcom device instruction: {candidate.get('romcom_device_instruction') or ''}")
            lines.append("If the Feed text depicts a teasing or fanservice-like mishap, keep it tasteful and non-explicit: no nudity, no exposed intimate body parts, no sexual framing. Focus on the concrete prop/action and the character's reaction.")
        if co_character_name:
            lines.append(f"Co-character: {co_character_name}")
            lines.append("This is a duo/interactions post: include the co-character if possible, and make their interaction readable through posture, distance, eye contact, gesture, or shared trouble.")
            if co_character.get("character_summary"):
                lines.append(f"Co-character overview: {co_character.get('character_summary')}")
            if co_character.get("appearance"):
                lines.append(f"Co-character appearance: {co_character.get('appearance')}")
            if co_character.get("art_style"):
                lines.append(f"Co-character art style: {co_character.get('art_style')}")
            lines.append("The co-character must match the target character's rendering fidelity, lighting model, anatomy detail, and high-end 3D semi-realistic finish.")
        else:
            lines.append("This is a solo post. Do not depict any other named character from the project, even if a name appears in the Feed text by mistake. Use only anonymous staff, customers, witnesses, or silhouettes as secondary figures.")
        visual_direction = self._feed_visual_direction_for_pattern(post_pattern)
        if visual_direction:
            lines.append(f"Visual direction: {visual_direction}")
        if project:
            lines.append(f"World: {project.title}. {project.summary or ''}")
        if world:
            lines.append(f"World setting: {world.overview or ''} {world.tone or ''}")
        if character:
            lines.append(f"Character: {character.name}")
            if character.nickname:
                lines.append(f"Nickname: {character.nickname}")
            if getattr(character, "character_summary", None):
                lines.append(f"Character overview: {character.character_summary}")
            if character.appearance_summary:
                lines.append(f"Appearance: {character.appearance_summary}")
            if character.personality:
                lines.append(f"Personality: {character.personality}")
            if character.art_style:
                lines.append(f"Art style: {character.art_style}")
            if character.ng_rules:
                lines.append(f"Never violate: {character.ng_rules}")
        lines.append("If safety-sensitive wording appears in the post, preserve intent while converting it into tasteful, non-explicit visual novel promotional art.")
        return "\n".join(lines)

    def _build_photobook_image_prompt(self, post, character, project, world, candidate: dict) -> str:
        scene_anchor = candidate.get("scene_anchor") if isinstance(candidate.get("scene_anchor"), dict) else {}
        lines = [
            "Create a single beautiful photobook-style character image for an X post.",
            "The goal is simple: cute, clean, pretty, immediately likable. Do not make it complex, funny, lore-heavy, or text-heavy.",
            "Use the reference image as the primary source of character identity, face, hairstyle, color palette, rendering quality, and design logic.",
            "Keep the character tasteful and non-explicit: no nudity, no lingerie, no sexual framing, no transparent clothing over intimate areas.",
            "No speech bubbles, no captions, no subtitles, no logo, no watermark, no UI overlay.",
            "High-end semi-realistic anime game-CG finish, soft skin rendering, delicate hair detail, cinematic bokeh, polished social-media illustration.",
            "Make it feel like a page from a cute character photobook: quiet pose, pretty light, clean background, gentle expression.",
            "The image should be attractive even if the viewer reads no text.",
        ]
        if scene_anchor.get("place_prompt"):
            lines.append(f"Background/location: {scene_anchor.get('place_prompt')}")
        elif scene_anchor.get("place"):
            lines.append(f"Background/location: {scene_anchor.get('place')}")
        if scene_anchor.get("outfit_prompt"):
            lines.append(f"Outfit: {scene_anchor.get('outfit_prompt')}")
        if scene_anchor.get("composition_prompt"):
            lines.append(f"Composition: {scene_anchor.get('composition_prompt')}")
        scene_brief = str(candidate.get("scene_brief") or "").strip()
        if scene_brief:
            lines.append(f"Scene brief: {scene_brief}")
        lines.append(f"Post caption: {post.body}")
        if project:
            lines.append(f"World: {project.title}. {project.summary or ''}")
        if world:
            lines.append(f"World setting mood: {world.overview or ''} {world.tone or ''}")
        if character:
            lines.append(f"Character: {character.name}")
            if character.nickname:
                lines.append(f"Nickname: {character.nickname}")
            if getattr(character, "character_summary", None):
                lines.append(f"Character overview: {character.character_summary}")
            if character.appearance_summary:
                lines.append(f"Appearance: {character.appearance_summary}")
            if character.art_style:
                lines.append(f"Art style: {character.art_style}")
            if character.ng_rules:
                lines.append(f"Never violate: {character.ng_rules}")
        lines.append("If the character is a shrine maiden, guide maiden, miko, or similar, lean into elegant shrine accessories, beads, cords, soft white fabric, warm sunset lantern light, and the attached-reference vibe.")
        return "\n".join(lines)

    def _feed_visual_direction_for_pattern(self, post_pattern: str) -> str:
        directions = {
            "速報・事件型": "Show the moment after a small incident: warning lights, confused bystanders implied by framing, the character reacting to the visible cause.",
            "炎上しかけ型": "Show the character caught after a controversial statement or mistake, with tense lighting and a comedic evidence object nearby.",
            "目撃情報型": "Use a candid surveillance-photo feeling: the character mid-action, slightly surprised, with the odd behavior clearly visible.",
            "ゆるい事故報告型": "Show a harmless malfunction or mess in progress, with the character trying to recover composure.",
            "キャラの自爆投稿型": "Show the character realizing they revealed too much: embarrassed face, phone or console nearby, awkward body language.",
            "意味深ポエムからのオチ型": "Start visually beautiful but include a clear ridiculous detail that undercuts the mood.",
            "アンケート型": "Show the character facing three or four visible choices as objects or signs, reacting as if none are safe.",
            "引用RT風ツッコミ型": "Show the quote source as a visible sign, terminal, or notice while the character reacts with disbelief.",
            "現地レポ型": "Frame it like a live field report without captions or speech bubbles: character in foreground, incident unfolding behind them. In-world signs, boards, or terminal text are allowed if they explain the scene.",
            "怪文書型": "Show an official-looking notice board or terminal causing absurd confusion, with the character caught reading it.",
            "キャラ同士の小競り合い型": "Show the target character in a lively argument or standoff with another implied character, using gesture and distance.",
            "お知らせなのに変型": "Show a formal announcement setting with one obviously absurd rule or object disrupting it.",
            "デートスポット異常型": "Show a romantic facility malfunctioning in an awkwardly intimate way, with the character visibly flustered.",
            "キャラの本音漏れ型": "Show a small private reaction accidentally exposed in public: blush, startled look, or hidden note/device.",
            "都市伝説型": "Show the rumored phenomenon with a plausible funny cause visible in the same frame.",
            "業務連絡風コメディ型": "Show workplace chaos: signs, devices, or staff-area props misbehaving while the character handles it.",
            "失敗写真の添え文型": "Compose it as a failed photo: the character posed for a nice shot, but a ridiculous background detail ruins it.",
            "小さな恋愛事件型": "Show a tiny romantic accident as if it were dramatic evidence: red lighting, awkward distance, hand/eye contact, flustered reaction.",
            "食べ物事故型": "Show a food item causing trouble: strange dish, messy reaction, steam, sauce, or a ranking/diagnostic device reacting.",
            "キャラ別名物ネタ型": "Make the character's signature theme visually central and active, not a passive portrait.",
        }
        return directions.get(post_pattern, "")

    def _store_generated_feed_image(self, project_id: int, post_id: int, image_base64: str):
        try:
            raw_bytes = base64.b64decode(image_base64)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("generated image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT") or os.path.join(os.getcwd(), "storage")
        output_dir = os.path.join(storage_root, "projects", str(project_id), "generated", "feed", str(post_id))
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_name = f"feed_{post_id}_{timestamp}.png"
        file_path = os.path.join(output_dir, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(raw_bytes)
        return file_name, file_path, len(raw_bytes)

    def refresh_character_feed_profile(self, character_id: int):
        posts = self._repo.list_posts(character_id=character_id, statuses=["published"], limit=80)
        latest_id = posts[0].id if posts else None
        if not posts:
            return self._repo.upsert_profile(
                character_id,
                {"profile_text": "", "source_post_count": 0, "source_latest_post_id": None, "summary_state_json": None},
            )
        try:
            profile = self._generate_feed_profile(character_id, posts)
        except Exception:
            current_app.logger.exception("feed profile refresh failed")
            return self._repo.get_profile(character_id)
        return self._repo.upsert_profile(
            character_id,
            {
                "profile_text": profile.get("profile_text") or "",
                "source_post_count": len(posts),
                "source_latest_post_id": latest_id,
                "summary_state_json": json_util.dumps(profile),
            },
        )

    def _generate_feed_profile(self, character_id: int, posts):
        character = self._character_service.get_character(character_id)
        post_lines = "\n".join(f"- {post.body}" for post in posts[:40])
        prompt = f"""
Return only JSON.
Summarize public Feed posts into a compact character profile supplement for live chat.
Do not overwrite explicit character settings. Extract tendencies visible from posts.

JSON keys:
{{
  "profile_text": "Japanese summary, 400 chars max",
  "likes": ["..."],
  "speech_tendencies": ["..."],
  "conversation_hooks": ["..."]
}}

Character:
name: {getattr(character, "name", "")}
nickname: {getattr(character, "nickname", "")}
personality: {getattr(character, "personality", "")}
speech_style: {getattr(character, "speech_style", "")}

Feed posts:
{post_lines}
"""
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.35,
            response_format={"type": "json_object"},
            max_tokens=900,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        return parsed if isinstance(parsed, dict) else {"profile_text": ""}

    def get_character_feed_profile(self, character_id: int):
        profile = self._repo.get_profile(character_id)
        if not profile:
            return None
        return {
            "character_id": profile.character_id,
            "profile_text": profile.profile_text or "",
            "source_post_count": profile.source_post_count or 0,
            "source_latest_post_id": profile.source_latest_post_id,
            "summary_state": self._load_json(profile.summary_state_json),
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        }
