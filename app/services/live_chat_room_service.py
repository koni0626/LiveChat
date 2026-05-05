from __future__ import annotations

import os
import random

from flask import current_app

from ..utils import json_util
from ..repositories.chat_session_repository import ChatSessionRepository
from ..repositories.live_chat_room_repository import LiveChatRoomRepository
from ..repositories.world_location_repository import WorldLocationRepository
from .asset_service import AssetService
from .character_service import CharacterService
from .closet_service import ClosetService
from .project_service import ProjectService
from .session_state_service import SessionStateService
from ..clients.text_ai_client import TextAIClient


class LiveChatRoomService:
    VALID_STATUSES = {"draft", "published", "archived"}

    def __init__(
        self,
        repository: LiveChatRoomRepository | None = None,
        project_service: ProjectService | None = None,
        character_service: CharacterService | None = None,
        chat_session_repository: ChatSessionRepository | None = None,
        asset_service: AssetService | None = None,
        closet_service: ClosetService | None = None,
        session_state_service: SessionStateService | None = None,
        text_ai_client: TextAIClient | None = None,
        world_location_repository: WorldLocationRepository | None = None,
    ):
        self._repo = repository or LiveChatRoomRepository()
        self._project_service = project_service or ProjectService()
        self._character_service = character_service or CharacterService()
        self._chat_session_repo = chat_session_repository or ChatSessionRepository()
        self._asset_service = asset_service or AssetService()
        self._closet_service = closet_service or ClosetService()
        self._session_state_service = session_state_service or SessionStateService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._world_location_repo = world_location_repository or WorldLocationRepository()

    def list_rooms(self, project_id: int, *, include_unpublished: bool = False):
        status = None if include_unpublished else "published"
        return self._repo.list_by_project(project_id, status=status)

    def get_room(self, room_id: int):
        return self._repo.get(room_id)

    def get_room_by_character(self, character_id: int):
        return self._repo.get_by_character(character_id)

    def serialize_room(self, room, *, include_counts: bool = False, owner_user_id: int | None = None):
        if not room:
            return None
        character = self._character_service.get_character(room.character_id)
        thumbnail_asset = self._serialize_asset_summary(getattr(character, "thumbnail_asset_id", None) if character else None)
        bromide_asset = self._serialize_asset_summary(getattr(character, "bromide_asset_id", None) if character else None)
        base_asset = self._serialize_asset_summary(getattr(character, "base_asset_id", None) if character else None)
        default_outfit = self._closet_service.serialize_outfit(
            self._closet_service.resolve_outfit(room.character_id, getattr(room, "default_outfit_id", None))
        ) if getattr(room, "default_outfit_id", None) else None
        payload = {
            "id": room.id,
            "project_id": room.project_id,
            "created_by_user_id": room.created_by_user_id,
            "character_id": room.character_id,
            "default_outfit_id": getattr(room, "default_outfit_id", None),
            "default_outfit": default_outfit,
            "title": room.title,
            "description": room.description,
            "conversation_objective": room.conversation_objective,
            "proxy_player_objective": getattr(room, "proxy_player_objective", None),
            "proxy_player_gender": getattr(room, "proxy_player_gender", None),
            "proxy_player_speech_style": getattr(room, "proxy_player_speech_style", None),
            "status": room.status,
            "sort_order": room.sort_order,
            "created_at": room.created_at.isoformat() if getattr(room, "created_at", None) else None,
            "updated_at": room.updated_at.isoformat() if getattr(room, "updated_at", None) else None,
            "character": (
                {
                    "id": character.id,
                    "name": character.name,
                    "nickname": getattr(character, "nickname", None),
                    "introduction_text": getattr(character, "introduction_text", None),
                    "thumbnail_asset_id": getattr(character, "thumbnail_asset_id", None),
                    "bromide_asset_id": getattr(character, "bromide_asset_id", None),
                    "base_asset_id": getattr(character, "base_asset_id", None),
                    "thumbnail_asset": thumbnail_asset,
                    "bromide_asset": bromide_asset,
                    "base_asset": base_asset,
                }
                if character
                else None
            ),
        }
        if include_counts:
            sessions = self._chat_session_repo.list_by_room(room.id)
            payload["session_count"] = len(sessions)
            if owner_user_id is not None:
                payload["my_session_count"] = len([item for item in sessions if item.owner_user_id == owner_user_id])
        return payload

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

    def _serialize_asset_summary(self, asset_id: int | None):
        if not asset_id:
            return None
        asset = self._asset_service.get_asset(asset_id)
        if not asset:
            return None
        return {
            "id": asset.id,
            "file_name": asset.file_name,
            "mime_type": asset.mime_type,
            "media_url": self._build_media_url(asset.file_path),
        }

    def serialize_rooms(self, rooms, *, include_counts: bool = False, owner_user_id: int | None = None):
        return [
            self.serialize_room(room, include_counts=include_counts, owner_user_id=owner_user_id)
            for room in rooms
        ]

    def create_room(self, project_id: int, payload: dict | None, created_by_user_id: int):
        payload = dict(payload or {})
        project = self._project_service.get_project(project_id)
        if not project:
            return None
        normalized = self._normalize_payload(project_id, payload, created_by_user_id=created_by_user_id, require_all=True)
        return self._repo.create(normalized)

    def build_objective_draft(self, project_id: int, payload: dict | None):
        payload = dict(payload or {})
        try:
            character_id = int(payload.get("character_id") or 0)
        except (TypeError, ValueError):
            character_id = 0
        if character_id <= 0:
            raise ValueError("character_id is required")
        character = self._character_service.get_character(character_id)
        if not character or character.project_id != project_id:
            raise ValueError("character_id is invalid")
        base_payload = self._character_service.build_default_live_chat_room_payload(character)
        return self._build_event_objective_draft(project_id, character, base_payload)

    def build_description_draft(self, project_id: int, payload: dict | None):
        payload = dict(payload or {})
        try:
            character_id = int(payload.get("character_id") or 0)
        except (TypeError, ValueError):
            character_id = 0
        if character_id <= 0:
            raise ValueError("character_id is required")
        character = self._character_service.get_character(character_id)
        if not character or character.project_id != project_id:
            raise ValueError("character_id is invalid")
        prompt = self._build_description_draft_prompt(character, payload)
        result = self._text_ai_client.generate_text(
            prompt,
            temperature=0.75,
            max_tokens=500,
        )
        text = self._normalize_description_text(result.get("text"))
        if not text:
            raise RuntimeError("description draft response is empty")
        return {"description": text}

    def update_room(self, room_id: int, payload: dict | None):
        payload = dict(payload or {})
        room = self.get_room(room_id)
        if not room:
            return None
        normalized = self._normalize_payload(
            room.project_id,
            payload,
            created_by_user_id=room.created_by_user_id,
            require_all=False,
            current_character_id=room.character_id,
        )
        if not normalized:
            raise ValueError("payload must not be empty")
        return self._repo.update(room_id, normalized)

    def _load_json_dict(self, value) -> dict:
        if not value:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if not isinstance(value, str):
            return {}
        try:
            parsed = json_util.loads(value)
        except Exception:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}

    def _build_room_settings(self, room) -> dict:
        return {
            "selected_character_ids": [room.character_id],
            "conversation_objective": room.conversation_objective,
            "proxy_player_objective": getattr(room, "proxy_player_objective", None),
            "proxy_player_gender": getattr(room, "proxy_player_gender", None),
            "proxy_player_speech_style": getattr(room, "proxy_player_speech_style", None),
        }

    def sync_room_to_sessions(self, room_id: int, *, owner_user_id: int | None = None) -> dict | None:
        room = self.get_room(room_id)
        if not room:
            return None
        snapshot = self.build_room_snapshot(room)
        room_settings = self._build_room_settings(room)
        sessions = self._chat_session_repo.list_by_room(room_id, owner_user_id=owner_user_id)
        synced_ids = []
        for session in sessions:
            settings = self._load_json_dict(getattr(session, "settings_json", None))
            settings.pop("selected_character_id", None)
            settings.update(room_settings)
            self._chat_session_repo.update(
                session.id,
                {
                    "room_snapshot_json": json_util.dumps(snapshot),
                    "settings_json": json_util.dumps(settings),
                },
            )
            state_row = self._session_state_service.get_state(session.id)
            state_json = self._load_json_dict(getattr(state_row, "state_json", None))
            state_json["active_character_ids"] = [room.character_id]
            state_json["room_id"] = room.id
            self._session_state_service.upsert_state(session.id, {"state_json": state_json})
            synced_ids.append(session.id)
        return {
            "room_id": room_id,
            "session_count": len(synced_ids),
            "session_ids": synced_ids,
        }

    def _build_description_draft_prompt(self, character, payload: dict) -> str:
        title = str(payload.get("title") or "").strip()
        objective = str(payload.get("conversation_objective") or "").strip()
        current_description = str(payload.get("description") or "").strip()
        lines = [
            "日本語で、ライブチャットのルーム紹介文を作成してください。",
            "ユーザーがルーム一覧で読み、どんな会話ができるか直感的に分かる短い紹介です。",
            "キャラクター本人の魅力、距離感、会話したくなる入口を入れてください。",
            "長さは120〜220字程度。Markdown、箇条書き、見出し、引用符、前置きは禁止。本文だけを返してください。",
            "",
            f"キャラクター名: {character.name}",
        ]
        for label, value in (
            ("ルーム名", title),
            ("既存の紹介文", current_description),
            ("キャラクター自己紹介", getattr(character, "introduction_text", None)),
            ("概要", getattr(character, "character_summary", None)),
            ("性格", getattr(character, "personality", None)),
            ("話し方", getattr(character, "speech_style", None)),
            ("セリフ例", getattr(character, "speech_sample", None)),
            ("見た目", getattr(character, "appearance_summary", None)),
            ("ルーム内の会話方針", objective),
        ):
            text = self._shorten_for_prompt(value, limit=700)
            if text:
                lines.append(f"{label}: {text}")
        return "\n".join(lines)

    def _build_event_objective_draft(self, project_id: int, character, base_payload: dict) -> dict:
        location = self._select_character_location(project_id, character.id)
        name = str(getattr(character, "name", None) or "このキャラクター").strip()
        facility_name = str(getattr(location, "name", None) or f"{name}の部屋").strip()
        facility_type = str(getattr(location, "location_type", None) or "").strip()
        facility_description = str(getattr(location, "description", None) or "").strip()
        fallback_room = location is None
        event = self._suggest_event_for_facility(facility_name, facility_type, facility_description, fallback_room)
        place_line = (
            f"施設は未登録なので、「{facility_name}」を利用する。"
            if fallback_room
            else f"施設は「{facility_name}」を利用する。"
        )
        ai_payload = self._build_ai_event_objective_draft(
            character,
            base_payload,
            facility_name=facility_name,
            facility_type=facility_type,
            facility_description=facility_description,
            fallback_room=fallback_room,
            event=event,
            place_line=place_line,
        )
        if ai_payload:
            return ai_payload
        room_title = f"{name}と{facility_name}"
        summary = self._shorten_for_prompt(getattr(character, "character_summary", None), limit=180)
        personality = self._shorten_for_prompt(getattr(character, "personality", None), limit=220)
        speech_style = self._shorten_for_prompt(getattr(character, "speech_style", None), limit=220)
        description_parts = [
            f"{name}が{facility_name}で、{event}についてプレイヤーと相談するためのルームです。",
            "目的がはっきりしているので、雑談だけで流れず、相談、選択、反応、次の約束へ進みます。",
        ]
        if summary:
            description_parts.append(summary)
        profile_lines = []
        for label, value in (
            ("キャラクター概要", summary),
            ("性格", personality),
            ("話し方", speech_style),
        ):
            if value:
                profile_lines.append(f"- {label}: {value}")
        if facility_type or facility_description:
            facility_detail = " / ".join(part for part in [facility_type, self._shorten_for_prompt(facility_description, limit=260)] if part)
            profile_lines.append(f"- 施設メモ: {facility_detail}")

        objective_lines = [
            f"{name}が{event}についてプレイヤーと相談する。",
            place_line,
            f"{facility_name}らしい具体的な選択肢を出し、プレイヤーに「どれがいいか」「どう思うか」を尋ねる。",
            f"プレイヤーが{name}のことを好きになるような発言をする。",
            f"{name}もプレイヤーの反応、優しさ、本気度に少しずつ惹かれていく。",
            "会話の最後には、次に一緒にやる小さな約束や未解決の楽しみを残す。",
            "",
            "## 会話の進め方",
            "- 最初の返答で、今何を相談しているのかを短く明言する。",
            "- 抽象的な勝負、運命、観測、影などだけで場を持たせず、目の前の施設と目的に結びつける。",
            "- 1回の返答につき、提案、質問、照れ、失敗、悩みのどれかを最低1つ入れる。",
            "- プレイヤーの発言を受けてから次の話題へ進む。勝手に結論を急がない。",
            "- 恋愛表現は押しつけず、キャラクター本人の魅力、迷い、可愛げ、笑いを混ぜて自然に出す。",
        ]
        if profile_lines:
            objective_lines.extend(["", "## キャラクターと施設の材料", *profile_lines])

        proxy_objective = "\n".join(
            [
                f"{name}と一緒に、{event}を楽しく具体的に決める。",
                f"{facility_name}で気になったもの、試したいもの、迷っているものを素直に伝える。",
                f"{name}の良いところを見つけたら、軽く褒めたり、照れさせたりする。",
                "相手が悩みや弱音を見せたら、急かさず受け止めて、次の小さな行動を提案する。",
            ]
        )
        payload = dict(base_payload or {})
        payload.update(
            {
                "title": room_title,
                "description": " ".join(description_parts),
                "conversation_objective": "\n".join(objective_lines),
                "proxy_player_objective": proxy_objective,
            }
        )
        return payload

    def _build_ai_event_objective_draft(
        self,
        character,
        base_payload: dict,
        *,
        facility_name: str,
        facility_type: str,
        facility_description: str,
        fallback_room: bool,
        event: str,
        place_line: str,
    ) -> dict | None:
        name = str(getattr(character, "name", None) or "このキャラクター").strip()
        variation_axes = [
            "小さな失敗から始まる相談",
            "相手の好みを探るデート相談",
            "キャラクター自身の悩みを混ぜた相談",
            "勝負や診断を使った軽い掛け合い",
            "次に一緒にやる約束を決める相談",
            "プレイヤーにだけ本音を漏らす相談",
            "施設の変な名物をどう楽しむかの相談",
            "キャラクターのこだわりと照れがぶつかる相談",
        ]
        axis = random.SystemRandom().choice(variation_axes)
        seed = random.SystemRandom().randint(100000, 999999)
        prompt = "\n".join(
            [
                "日本語で、ライブチャットルームの「キャラクターへの指示」を1案生成してください。",
                "同じキャラクターでも毎回違う会話目的になるように、下記の変化軸と乱数を必ず反映してください。",
                "説明や前置きは禁止。JSONオブジェクトだけを返してください。",
                "",
                "必須JSONキー:",
                "- title: 30字以内のルーム名",
                "- description: 80〜180字のルーム紹介文",
                "- conversation_objective: キャラクターへの指示。6〜10行程度。会話目的、施設、進め方、恋、笑い、悩みや本音を含める。",
                "- proxy_player_objective: 代理プレイヤーの目的。3〜5行程度。",
                "",
                "重要ルール:",
                "- 固定テンプレートを使わない。",
                "- 何について相談しているのかを最初の1行で明確にする。",
                "- 抽象的な運命、観測、影、勝負だけで場を持たせない。",
                "- プレイヤーがキャラクターを好きになりやすい、具体的でドキッとする発言を促す。",
                "- キャラクターも少しずつプレイヤーに惹かれる。",
                "- 笑い、照れ、失敗、悩み相談、キャラクター自身の本音を最低2つ以上混ぜる。",
                "- コスプレ、試着、衣装の施設でない限り、コスプレ相談にしない。",
                "- 施設が未登録の場合は、キャラクターの部屋でできる具体的な相談にする。",
                "",
                f"変化軸: {axis}",
                f"乱数: {seed}",
                "",
                f"キャラクター名: {name}",
                f"施設名: {facility_name}",
                f"施設タイプ: {facility_type or '未設定'}",
                f"施設説明: {self._shorten_for_prompt(facility_description, limit=700) or '未設定'}",
                f"施設未登録: {'はい' if fallback_room else 'いいえ'}",
                f"基本イベント候補: {event}",
                f"施設指定行: {place_line}",
            ]
        )
        for label, value in (
            ("概要", getattr(character, "character_summary", None)),
            ("性格", getattr(character, "personality", None)),
            ("話し方", getattr(character, "speech_style", None)),
            ("セリフ例", getattr(character, "speech_sample", None)),
            ("見た目", getattr(character, "appearance_summary", None)),
            ("会話メモ", getattr(character, "memory_notes", None)),
            ("NGルール", getattr(character, "ng_rules", None)),
        ):
            text = self._shorten_for_prompt(value, limit=700)
            if text:
                prompt += f"\n{label}: {text}"
        try:
            result = self._text_ai_client.generate_text(
                prompt,
                temperature=0.95,
                max_tokens=1100,
                response_format={"type": "json_object"},
            )
            parsed = json_util.loads(str(result.get("text") or "").strip())
        except Exception:
            return None
        if not isinstance(parsed, dict):
            return None
        title = self._normalize_description_text(parsed.get("title"))[:80]
        description = self._normalize_description_text(parsed.get("description"))
        objective = self._normalize_description_text(parsed.get("conversation_objective"))
        proxy_objective = self._normalize_description_text(parsed.get("proxy_player_objective"))
        if not title or not description or not objective:
            return None
        payload = dict(base_payload or {})
        payload.update(
            {
                "title": title,
                "description": description,
                "conversation_objective": objective,
                "proxy_player_objective": proxy_objective
                or "\n".join(
                    [
                        f"{name}と一緒に、{event}を具体的に決める。",
                        f"{facility_name}で気になったことや試したいことを伝える。",
                        f"{name}の反応を見ながら、少しずつ距離を縮める。",
                    ]
                ),
            }
        )
        return payload

    def _select_character_location(self, project_id: int, character_id: int):
        try:
            locations = self._world_location_repo.list_by_project(project_id)
        except Exception:
            return None
        owned = [
            location
            for location in locations
            if getattr(location, "owner_character_id", None) == character_id
            and getattr(location, "status", "published") != "archived"
        ]
        if not owned:
            return None
        published = [location for location in owned if getattr(location, "status", None) == "published"]
        candidates = published or owned
        outing_candidates = [
            location
            for location in candidates
            if not self._looks_like_private_room(getattr(location, "name", None), getattr(location, "location_type", None))
        ]
        return (outing_candidates or candidates)[0]

    def _looks_like_private_room(self, name: str | None, location_type: str | None) -> bool:
        text = f"{name or ''} {location_type or ''}"
        return any(keyword in text for keyword in ("の家", "自宅", "住居", "自室", "部屋", "私室", "寝室", "ホーム", "マンション", "アパート"))

    def _suggest_event_for_facility(self, name: str, location_type: str, description: str, fallback_room: bool) -> str:
        if fallback_room:
            return "部屋で一緒に過ごす日の予定や、今いちばん話したいこと"
        primary_text = f"{name} {location_type}".lower()
        text = f"{primary_text} {description}".lower()
        rules = [
            (("コスプレ", "試着", "衣装", "クローゼット", "更衣", "ドレスアップ"), "次に着る衣装やコスプレのテーマ"),
            (("撮影スタジオ", "フォトスタジオ", "写真スタジオ", "写真館", "フォト", "撮影"), "撮りたい記念写真やポーズ"),
            (("音楽スタジオ", "ダンススタジオ", "リハーサル", "レッスンスタジオ"), "披露したい演目や練習の見せ方"),
            (("水族館", "海", "プール", "アクア"), "一緒に見たい展示やデートの回り方"),
            (("庭園", "公園", "ガーデン", "空中庭園"), "散歩しながら見たい景色や休憩場所"),
            (("レストラン", "カフェ", "パーラー", "屋台", "スイーツ", "料理"), "注文するメニューや相手に食べてほしい一皿"),
            (("クラブ", "ライブ", "バー", "ラウンジ"), "今夜の過ごし方や盛り上げ方"),
            (("映画", "シネマ", "劇場"), "一緒に観る作品や上映後に話したい感想"),
            (("美術館", "資料館", "古書", "写真館", "展示"), "気になる展示や残したい記念写真"),
            (("アクセサリー", "ショップ", "市場", "オークション"), "選ぶ品物やプレゼント候補"),
            (("貸金庫", "投資", "金融", "銀行", "vip"), "預けたい秘密や挑戦する小さな勝負"),
            (("塔", "タワー", "観測", "展望"), "上から見たい景色やそこで交わす約束"),
            (("開発", "研究", "局", "ラボ"), "試したい発明や失敗した実験の立て直し"),
            (("会社", "カンパニー", "仕事"), "今日の仕事をどう乗り切るか"),
        ]
        for keywords, event in rules:
            if any(keyword in primary_text for keyword in keywords):
                return event
        for keywords, event in rules:
            if any(keyword in text for keyword in keywords):
                return event
        return f"{name}で一緒にやってみたいイベントや過ごし方"

    def _normalize_description_text(self, value) -> str:
        text = str(value or "").strip().replace("\r\n", "\n")
        if text.startswith("```"):
            text = text.strip("`").strip()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = " ".join(lines).strip()
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("「") and text.endswith("」")):
            text = text[1:-1].strip()
        return text[:600]

    def _shorten_for_prompt(self, value, limit: int = 500) -> str:
        text = str(value or "").strip().replace("\r\n", "\n")
        if len(text) <= limit:
            return text
        return text[:limit].rstrip() + "..."

    def delete_room(self, room_id: int):
        return self._repo.delete(room_id)

    def build_room_snapshot(self, room):
        character = self._character_service.get_character(room.character_id)
        default_outfit = self._closet_service.serialize_outfit(
            self._closet_service.resolve_outfit(room.character_id, getattr(room, "default_outfit_id", None))
        ) if getattr(room, "default_outfit_id", None) else None
        return {
            "room_id": room.id,
            "room_title": room.title,
            "conversation_objective": room.conversation_objective,
            "proxy_player_objective": getattr(room, "proxy_player_objective", None),
            "proxy_player_gender": getattr(room, "proxy_player_gender", None),
            "proxy_player_speech_style": getattr(room, "proxy_player_speech_style", None),
            "character_id": room.character_id,
            "character_name": character.name if character else None,
            "default_outfit_id": getattr(room, "default_outfit_id", None),
            "default_outfit_name": default_outfit.get("name") if isinstance(default_outfit, dict) else None,
            "status": room.status,
            "version_updated_at": room.updated_at.isoformat() if getattr(room, "updated_at", None) else None,
        }

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
        if require_all or "conversation_objective" in payload:
            objective = str(payload.get("conversation_objective") or "").strip()
            if not objective:
                raise ValueError("conversation_objective is required")
            normalized["conversation_objective"] = objective
        if "proxy_player_objective" in payload or require_all:
            normalized["proxy_player_objective"] = str(payload.get("proxy_player_objective") or "").strip() or None
        if "proxy_player_gender" in payload or require_all:
            normalized["proxy_player_gender"] = str(payload.get("proxy_player_gender") or "").strip() or None
        if "proxy_player_speech_style" in payload or require_all:
            normalized["proxy_player_speech_style"] = str(payload.get("proxy_player_speech_style") or "").strip() or None
        if "description" in payload:
            normalized["description"] = str(payload.get("description") or "").strip() or None
        if require_all or "character_id" in payload:
            try:
                character_id = int(payload.get("character_id") or 0)
            except (TypeError, ValueError):
                character_id = 0
            if character_id <= 0:
                raise ValueError("character_id is required")
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
                character_id_for_outfit = normalized.get("character_id") or effective_character_id
                outfit = self._closet_service.resolve_outfit(int(character_id_for_outfit or 0), outfit_id)
                if not outfit or outfit.id != outfit_id or outfit.project_id != project_id:
                    raise ValueError("default_outfit_id is invalid")
                normalized["default_outfit_id"] = outfit_id
            else:
                normalized["default_outfit_id"] = None
        if "status" in payload or require_all:
            status = str(payload.get("status") or "draft").strip() or "draft"
            if status not in self.VALID_STATUSES:
                raise ValueError("status is invalid")
            normalized["status"] = status
        if "sort_order" in payload:
            try:
                normalized["sort_order"] = int(payload.get("sort_order") or 0)
            except (TypeError, ValueError):
                normalized["sort_order"] = 0
        if require_all:
            normalized["project_id"] = project_id
            normalized["created_by_user_id"] = created_by_user_id
        return normalized
