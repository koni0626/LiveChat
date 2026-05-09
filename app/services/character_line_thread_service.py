from __future__ import annotations

import os
import random
import uuid
from datetime import datetime

from flask import current_app

from ..extensions import db
from ..clients.text_ai_client import TextAIClient
from ..models import Asset, CharacterLineMessage, CharacterLineRoom
from ..repositories.character_repository import CharacterRepository
from ..repositories.world_location_repository import WorldLocationRepository
from ..utils import json_util
from .project_service import ProjectService
from .world_service import WorldService
from .character_memory_note_service import CharacterMemoryNoteService
from .character_user_memory_service import CharacterUserMemoryService
from .asset_service import AssetService


LINE_THREAD_PATTERNS = [
    "強めのツッコミで会話を締める担当",
    "余計な一言で火に油を注ぐ担当",
    "本人をかばうつもりで逆に燃やす担当",
    "妙に冷静な分析で変な結論を出す担当",
    "全部を恋愛方向に誤読する担当",
    "話を脱線させて謎の具体物を持ち込む担当",
    "前に出た言葉を天丼して笑いにする担当",
    "最後に伏線を回収してオチをつける担当",
]

COMEDY_BEATS = [
    "火種: テーマ名そのものにツッコむ",
    "誤読: 露骨な話を服装審査、恋愛相談、都市規約などにズラす",
    "拡大: 誰かが勝手に公式会議や監査にする",
    "天丼: 変な単語を2回目以降で少し形を変えて再利用する",
    "逆張り: かばう発言が一番ひどい燃料になる",
    "具体物: 看板、通知名、議事録、スタンプ、グループ名などLINEっぽい小物で落とす",
    "回収: 最後に序盤の言葉やグループ名を回収してオチにする",
]

LINE_STORY_PHASES = [
    "1. 火種: テーマ名に軽くツッコむ",
    "2. 乗っかり: 別キャラが雑に茶化す",
    "3. 制止: 誰かが本人不在で話す危うさを軽く止める",
    "4. ずらし: 言い方やグループ名など別の笑いにずらす",
    "5. 天丼: 序盤の言葉をもう一回だけ使う",
    "6. 本題回帰: ちゃんとテーマへ戻る",
    "7. オチ準備: 誰かが変な結論を出しかける",
    "8. オチ: 短くスクショ向きに落とす",
]


class CharacterLineThreadService:
    def __init__(
        self,
        *,
        character_repository: CharacterRepository | None = None,
        project_service: ProjectService | None = None,
        world_service: WorldService | None = None,
        text_ai_client: TextAIClient | None = None,
        character_memory_note_service: CharacterMemoryNoteService | None = None,
        character_user_memory_service: CharacterUserMemoryService | None = None,
        world_location_repository: WorldLocationRepository | None = None,
        asset_service: AssetService | None = None,
    ):
        self._characters = character_repository or CharacterRepository()
        self._projects = project_service or ProjectService()
        self._worlds = world_service or WorldService()
        self._text_ai_client = text_ai_client or TextAIClient()
        self._character_memory_notes = character_memory_note_service or CharacterMemoryNoteService()
        self._character_user_memory = character_user_memory_service or CharacterUserMemoryService()
        self._world_locations = world_location_repository or WorldLocationRepository()
        self._assets = asset_service or AssetService()

    def list_rooms(self, *, project_id: int, user_id: int) -> list[dict]:
        self._ensure_default_room(project_id=project_id, user_id=user_id)
        rooms = (
            CharacterLineRoom.query.filter(
                CharacterLineRoom.project_id == project_id,
                CharacterLineRoom.deleted_at.is_(None),
            )
            .order_by(CharacterLineRoom.is_default.desc(), CharacterLineRoom.last_message_at.desc().nullslast(), CharacterLineRoom.id.desc())
            .all()
        )
        return [self.serialize_room(room) for room in rooms]

    def create_room(self, *, project_id: int, user_id: int, payload: dict) -> dict:
        title = str(payload.get("title") or "").strip()[:255] or "LINEルーム"
        participant_ids = self._normalize_participant_ids(project_id, payload.get("participant_ids") or [])
        room = CharacterLineRoom(
            project_id=project_id,
            created_by_user_id=user_id,
            title=title,
            participant_ids_json=json_util.dumps(participant_ids),
            is_default=False,
        )
        db.session.add(room)
        db.session.commit()
        return self.serialize_room(room)

    def get_room_payload(self, *, room_id: int) -> dict | None:
        room = self._get_room(room_id)
        if not room:
            return None
        return {
            "room": self.serialize_room(room),
            "participants": [self._serialize_character(character) for character in self._room_participants(room)],
            "messages": [self.serialize_message(message) for message in self._room_messages(room.id, limit=120)],
        }

    def generate_room_reply(
        self,
        *,
        room_id: int,
        user_id: int,
        body: str,
        turns: int = 20,
        exact_turns: bool = False,
        use_ai: bool = True,
        upload_file=None,
    ) -> dict:
        room = self._get_room(room_id)
        if not room:
            raise LookupError("room not found")
        body = str(body or "").strip()
        if not body:
            if upload_file is None:
                raise ValueError("message is required")
            body = "写真を送信"
        batch_id = uuid.uuid4().hex[:12]
        next_turn = self._next_turn_index(room.id)
        recent_history = self._room_history_context(room, limit=40)
        image_asset = None
        image_observation = None
        if upload_file is not None:
            image_asset, image_observation = self._store_and_analyze_upload(room, upload_file)
            if image_observation:
                body = f"{body}\n[写真: {image_observation.get('short_description') or image_observation.get('label') or '画像'}]"[:2000]
        player_metadata = {}
        if image_asset:
            player_metadata["image_asset_id"] = image_asset.id
        if image_observation:
            player_metadata["image_observation"] = image_observation
        player_message = CharacterLineMessage(
            room_id=room.id,
            project_id=room.project_id,
            sender_type="player",
            user_id=user_id,
            body=body[:2000],
            turn_index=next_turn,
            generation_batch=batch_id,
            metadata_json=json_util.dumps(player_metadata) if player_metadata else None,
        )
        db.session.add(player_message)
        db.session.commit()

        participants = self._room_participants(room)
        long_term_memories = self._participant_memory_context(user_id=user_id, participants=participants)
        thread = self.generate_thread(
            project_id=room.project_id,
            theme=body,
            turns=turns,
            participant_count=len(participants) or 8,
            player_comment=None,
            exact_turns=exact_turns,
            use_ai=use_ai,
            participants=participants,
            conversation_history=recent_history,
            long_term_memories=long_term_memories,
            uploaded_image_observation=image_observation,
        )
        created = []
        turn_index = next_turn + 1
        for item in thread.get("messages") or []:
            message = CharacterLineMessage(
                room_id=room.id,
                project_id=room.project_id,
                sender_type="character",
                character_id=item.get("speaker_id"),
                body=str(item.get("text") or "").strip()[:2000],
                turn_index=turn_index,
                generation_batch=batch_id,
                metadata_json=json_util.dumps({"theme": body, "punchline": thread.get("punchline")}),
            )
            db.session.add(message)
            created.append(message)
            turn_index += 1
        room.last_theme = body
        room.last_message_at = datetime.utcnow()
        db.session.commit()
        created_memories = []
        if use_ai:
            created_memories = self._extract_line_memories(
                user_id=user_id,
                room=room,
                participants=participants,
                messages=[player_message, *created],
                source_ref=f"character_line_room:{room.id}:{batch_id}",
            )
        return {
            "room": self.serialize_room(room),
            "player_message": self.serialize_message(player_message),
            "messages": [self.serialize_message(message) for message in created],
            "punchline": thread.get("punchline"),
            "batch_id": batch_id,
            "created_memories": created_memories,
        }

    def generate_thread(
        self,
        *,
        project_id: int,
        theme: str,
        turns: int = 20,
        participant_count: int = 8,
        player_comment: str | None = None,
        exact_turns: bool = False,
        use_ai: bool = True,
        participants: list | None = None,
        conversation_history: list[dict] | None = None,
        long_term_memories: list[dict] | None = None,
        uploaded_image_observation: dict | None = None,
    ) -> dict:
        project = self._projects.get_project(project_id)
        if not project:
            raise LookupError("project not found")
        theme = str(theme or "").strip()
        if not theme:
            raise ValueError("theme is required")
        max_turns = max(4, min(int(turns or 20), 40))
        min_turns = 4

        characters = participants or self._characters.list_by_project(project_id)
        if not characters:
            raise ValueError("project has no characters")
        selected_participants = list(characters) if participants else self._select_participants(characters, participant_count)
        plan = self._build_manager_plan(selected_participants, theme=theme, turns=max_turns)
        location_index = self._location_index_context(project_id, selected_participants)
        participant_presence = self._participant_presence_context(selected_participants)

        if use_ai:
            try:
                generated = self._generate_line_thread(
                    project=project,
                    participants=selected_participants,
                    theme=theme,
                    min_turns=min_turns,
                    max_turns=max_turns,
                    exact_turns=exact_turns,
                    player_comment=player_comment,
                    plan=plan,
                    conversation_history=conversation_history or [],
                    long_term_memories=long_term_memories or [],
                    location_index=location_index,
                    uploaded_image_observation=uploaded_image_observation or {},
                    participant_presence=participant_presence,
                )
                if generated:
                    return generated
            except Exception:
                pass
        return self._fallback_thread(
            project_id=project_id,
            theme=theme,
            turns=max_turns if exact_turns else min(max_turns, max(min_turns, 10)),
            player_comment=player_comment,
            participants=selected_participants,
            plan=plan,
            exact_turns=exact_turns,
            conversation_history=conversation_history or [],
            long_term_memories=long_term_memories or [],
            location_index=location_index,
            uploaded_image_observation=uploaded_image_observation or {},
            participant_presence=participant_presence,
        )

    def format_thread_text(self, thread: dict) -> str:
        lines = [
            f"# {thread.get('title') or 'キャラクターLINE'}",
            f"theme: {thread.get('theme') or ''}",
        ]
        if thread.get("player_comment"):
            lines.append(f"player: {thread.get('player_comment')}")
        lines.append("")
        for message in thread.get("messages") or []:
            turn = message.get("turn")
            speaker = message.get("speaker_name") or "?"
            text = message.get("text") or ""
            lines.append(f"{turn:02d}. {speaker}: {text}")
        if thread.get("punchline"):
            lines.extend(["", f"オチ: {thread['punchline']}"])
        return "\n".join(lines)

    def serialize_room(self, room: CharacterLineRoom) -> dict:
        participant_ids = self._room_participant_ids(room)
        messages = self._room_messages(room.id, limit=1)
        return {
            "id": room.id,
            "project_id": room.project_id,
            "title": room.title,
            "is_default": bool(room.is_default),
            "participant_ids": participant_ids,
            "participant_count": len(participant_ids) if participant_ids else self._characters_count(room.project_id),
            "last_theme": room.last_theme,
            "last_message_at": room.last_message_at.isoformat() if room.last_message_at else None,
            "latest_message": self.serialize_message(messages[-1]) if messages else None,
        }

    def serialize_message(self, message: CharacterLineMessage) -> dict:
        character = self._characters.get(message.character_id) if message.character_id else None
        metadata = self._load_json(getattr(message, "metadata_json", None))
        image_asset = self._serialize_asset(metadata.get("image_asset_id")) if metadata.get("image_asset_id") else None
        return {
            "id": message.id,
            "room_id": message.room_id,
            "sender_type": message.sender_type,
            "character_id": message.character_id,
            "user_id": message.user_id,
            "body": message.body,
            "turn_index": message.turn_index,
            "generation_batch": message.generation_batch,
            "metadata": metadata,
            "image_asset": image_asset,
            "image_observation": metadata.get("image_observation") if isinstance(metadata.get("image_observation"), dict) else None,
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "character": self._serialize_character(character) if character else None,
        }

    def _ensure_default_room(self, *, project_id: int, user_id: int) -> CharacterLineRoom:
        room = CharacterLineRoom.query.filter(
            CharacterLineRoom.project_id == project_id,
            CharacterLineRoom.is_default.is_(True),
            CharacterLineRoom.deleted_at.is_(None),
        ).first()
        if room:
            return room
        room = CharacterLineRoom(
            project_id=project_id,
            created_by_user_id=user_id,
            title="全員LINE",
            participant_ids_json=None,
            is_default=True,
        )
        db.session.add(room)
        db.session.commit()
        return room

    def _get_room(self, room_id: int):
        return CharacterLineRoom.query.filter(
            CharacterLineRoom.id == room_id,
            CharacterLineRoom.deleted_at.is_(None),
        ).first()

    def _room_messages(self, room_id: int, *, limit: int = 120):
        return list(
            reversed(
                CharacterLineMessage.query.filter(
                    CharacterLineMessage.room_id == room_id,
                    CharacterLineMessage.deleted_at.is_(None),
                )
                .order_by(CharacterLineMessage.turn_index.desc(), CharacterLineMessage.id.desc())
                .limit(max(1, min(int(limit or 120), 300)))
                .all()
            )
        )

    def _room_history_context(self, room: CharacterLineRoom, *, limit: int = 40) -> list[dict]:
        messages = self._room_messages(room.id, limit=limit)
        return [self._message_context(message) for message in messages]

    def _message_context(self, message: CharacterLineMessage) -> dict:
        character = self._characters.get(message.character_id) if message.character_id else None
        speaker_name = "Player" if message.sender_type == "player" else getattr(character, "name", None) or "Character"
        metadata = self._load_json(getattr(message, "metadata_json", None))
        observation = metadata.get("image_observation") if isinstance(metadata.get("image_observation"), dict) else None
        return {
            "turn_index": message.turn_index,
            "sender_type": message.sender_type,
            "speaker_id": message.character_id,
            "speaker_name": speaker_name,
            "text": str(message.body or "")[:500],
            "image_observation": observation,
        }

    def _load_json(self, value) -> dict:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json_util.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _store_and_analyze_upload(self, room: CharacterLineRoom, upload_file):
        asset = self._assets.create_asset(
            room.project_id,
            {
                "asset_type": "character_line_upload_image",
                "upload_file": upload_file,
                "metadata_json": json_util.dumps({"source": "character_line_upload", "room_id": room.id}),
            },
        )
        observation = self._analyze_line_image(asset.file_path)
        metadata = self._load_json(asset.metadata_json)
        metadata["image_observation"] = observation
        try:
            self._assets.update_asset(asset.id, {"metadata_json": json_util.dumps(metadata)})
        except Exception:
            pass
        return asset, observation

    def _analyze_line_image(self, file_path: str | None) -> dict:
        if not file_path:
            return {}
        prompt = """
Return only JSON.
Describe this uploaded photo so characters in a Japanese LINE-style group chat can react to it naturally.
Required keys:
- label: short Japanese label
- short_description: 1-2 Japanese sentences, concrete and visual
- visible_subjects: array of short Japanese strings
- mood: short Japanese phrase
- conversation_hooks: array of 3-6 short Japanese strings characters could tease, notice, or ask about
- sensitivity_note: short Japanese safety note if relevant, otherwise empty string
Do not identify real people. Do not infer private identity. If the image is sexual or sensitive, describe it in neutral, non-explicit terms.
""".strip()
        try:
            result = self._text_ai_client.analyze_image(file_path, prompt=prompt)
            parsed = result.get("parsed_json") or {}
        except Exception:
            return {"label": "写真", "short_description": "アップロードされた写真。", "visible_subjects": [], "mood": "", "conversation_hooks": []}
        if not isinstance(parsed, dict):
            parsed = {}
        return {
            "label": str(parsed.get("label") or "写真").strip()[:80],
            "short_description": str(parsed.get("short_description") or parsed.get("description") or "アップロードされた写真。").strip()[:500],
            "visible_subjects": [str(item).strip()[:80] for item in (parsed.get("visible_subjects") or []) if str(item or "").strip()][:10],
            "mood": str(parsed.get("mood") or "").strip()[:120],
            "conversation_hooks": [str(item).strip()[:120] for item in (parsed.get("conversation_hooks") or []) if str(item or "").strip()][:8],
            "sensitivity_note": str(parsed.get("sensitivity_note") or "").strip()[:200],
        }

    def _participant_memory_context(self, *, user_id: int, participants: list) -> list[dict]:
        memories = []
        for character in participants:
            character_id = int(getattr(character, "id", 0) or 0)
            if not character_id:
                continue
            notes_block = self._character_memory_notes.build_prompt_block(user_id, character_id, limit=8)
            user_memory_block = self._character_user_memory.build_prompt_block(user_id, character_id)
            if not notes_block and not user_memory_block:
                continue
            memories.append(
                {
                    "character_id": character_id,
                    "character_name": getattr(character, "name", None),
                    "memory_notes": notes_block,
                    "player_relationship_memory": user_memory_block,
                }
            )
        return memories

    def _participant_presence_context(self, participants: list) -> dict:
        return {
            "room_participants": [
                {
                    "id": int(getattr(character, "id", 0) or 0),
                    "name": getattr(character, "name", None),
                }
                for character in participants
            ],
            "presence_rule": "All listed room_participants are currently in this LINE room and can read the chat.",
        }

    def _location_index_context(self, project_id: int, participants: list) -> list[dict]:
        locations = self._world_locations.list_by_project(project_id)
        if not locations:
            return []
        participants_by_id = {int(getattr(character, "id", 0) or 0): character for character in participants}
        all_characters_by_id = {int(character.id): character for character in self._characters.list_by_project(project_id)}
        index = []
        for location in locations:
            owner_id = int(getattr(location, "owner_character_id", 0) or 0)
            owner = all_characters_by_id.get(owner_id)
            index.append(
                {
                    "id": location.id,
                    "name": location.name,
                    "region": getattr(location, "region", None),
                    "type": location.location_type,
                    "tags": self._tags_from_json(getattr(location, "tags_json", None))[:6],
                    "owner_character_id": owner_id or None,
                    "owner_name": getattr(owner, "name", None) if owner else None,
                    "owner_is_participant": owner_id in participants_by_id,
                    "one_line": self._shorten(location.description, 80),
                }
            )
        return index

    def _tags_from_json(self, raw_value) -> list[str]:
        if not raw_value:
            return []
        try:
            values = json_util.loads(raw_value)
        except Exception:
            values = []
        if not isinstance(values, list):
            return []
        return [str(value).strip() for value in values if str(value or "").strip()]

    def _shorten(self, value: str | None, limit: int) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 1)].rstrip() + "…"

    def _extract_line_memories(
        self,
        *,
        user_id: int,
        room: CharacterLineRoom,
        participants: list,
        messages: list[CharacterLineMessage],
        source_ref: str,
    ) -> list[dict]:
        if not user_id or len(messages) < 3:
            return []
        lines = []
        for message in messages[-30:]:
            context = self._message_context(message)
            text = context.get("text")
            if text:
                lines.append(f"{context.get('speaker_name')}: {text}")
        if not lines:
            return []
        created = []
        for character in participants:
            character_id = int(getattr(character, "id", 0) or 0)
            if not character_id:
                continue
            character_created = []
            existing = self._character_memory_notes.build_prompt_block(user_id, character_id, limit=12)
            prompt = "\n".join(
                [
                    "Extract durable character memory notes from this LINE-style group chat.",
                    "Return only JSON: {\"notes\":[{\"category\":\"relationship|foreshadowing|fun_fact|other\",\"note\":\"short Japanese remembered event\",\"confidence\":0.0}]}",
                    "Create notes only for remembered events: a small incident, shared memory, in-joke, nickname born in the chat, promise, unresolved topic, or photo-related happening.",
                    "Each note must read like a past memory. Prefer Japanese phrasing that starts with '以前LINEで', 'LINEで', 'あの時', or '前に'.",
                    "The note must include who did what and why the group may remember it later.",
                    "Do not extract personality traits, habits, preferences, values, weaknesses, speaking style, or permanent character facts.",
                    "Do not write notes like 'X has a habit of...' or 'X tends to...'. Convert only concrete events into memories.",
                    "Do not store generic summaries, obvious facts, one-off jokes with no future value, or private player profile facts.",
                    "Do not rewrite the permanent character profile. These are lightweight memories of things that happened in this LINE room.",
                    f"Room title: {room.title or 'LINE'}",
                    f"Target character: {getattr(character, 'name', None) or 'character'}",
                    f"Target character profile: {getattr(character, 'character_summary', None) or ''}",
                    f"Existing memory notes:\n{existing or '(none)'}",
                    "Recent LINE messages:",
                    *lines,
                ]
            )
            try:
                result = self._text_ai_client.generate_text(
                    prompt,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    max_tokens=900,
                )
                parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
            except Exception:
                continue
            for item in parsed.get("notes") or []:
                if not isinstance(item, dict):
                    continue
                note = str(item.get("note") or "").strip()[:1000]
                try:
                    confidence = float(item.get("confidence", 0))
                except (TypeError, ValueError):
                    confidence = 0
                if not note or confidence < 0.55:
                    continue
                if self._looks_like_trait_memory(note):
                    continue
                if self._character_memory_notes.has_duplicate(user_id, character_id, note):
                    continue
                category = item.get("category") or "other"
                if category not in {"relationship", "foreshadowing", "fun_fact", "other"}:
                    category = "other"
                row = self._character_memory_notes.create_note(
                    user_id,
                    character_id,
                    {
                        "category": category,
                        "note": note,
                        "confidence": confidence,
                        "enabled": True,
                        "source_ref": source_ref,
                    },
                    source_type="character_line_ai",
                )
                serialized = self._character_memory_notes.serialize_note(row)
                created.append(serialized)
                character_created.append(serialized)
            if character_created:
                self._character_memory_notes.summarize_if_needed(
                    self._text_ai_client,
                    user_id,
                    self._character_context(character),
                )
        return created

    def _looks_like_trait_memory(self, note: str) -> bool:
        value = str(note or "").strip()
        if not value:
            return True
        trait_markers = (
            "癖がある",
            "傾向がある",
            "好む",
            "苦手",
            "重視する",
            "しがち",
            "しやすい",
            "口調",
            "話し方",
            "性格",
            "価値観",
            "弱点",
            "特徴",
            "habit",
            "tends to",
            "preference",
            "weakness",
            "value",
        )
        return any(marker in value for marker in trait_markers)

    def _next_turn_index(self, room_id: int) -> int:
        latest = (
            CharacterLineMessage.query.filter(
                CharacterLineMessage.room_id == room_id,
                CharacterLineMessage.deleted_at.is_(None),
            )
            .order_by(CharacterLineMessage.turn_index.desc(), CharacterLineMessage.id.desc())
            .first()
        )
        return int(getattr(latest, "turn_index", 0) or 0) + 1

    def _room_participant_ids(self, room: CharacterLineRoom) -> list[int]:
        if not room.participant_ids_json:
            return []
        try:
            values = json_util.loads(room.participant_ids_json)
        except Exception:
            values = []
        ids = []
        for value in values or []:
            try:
                character_id = int(value or 0)
            except (TypeError, ValueError):
                continue
            if character_id:
                ids.append(character_id)
        return ids

    def _room_participants(self, room: CharacterLineRoom) -> list:
        ids = self._room_participant_ids(room)
        characters = self._characters.list_by_project(room.project_id)
        if not ids:
            return characters
        by_id = {int(character.id): character for character in characters}
        return [by_id[character_id] for character_id in ids if character_id in by_id]

    def _normalize_participant_ids(self, project_id: int, values: list) -> list[int]:
        valid_ids = {int(character.id) for character in self._characters.list_by_project(project_id)}
        normalized = []
        for value in values or []:
            try:
                character_id = int(value or 0)
            except (TypeError, ValueError):
                continue
            if character_id in valid_ids and character_id not in normalized:
                normalized.append(character_id)
        return normalized

    def _characters_count(self, project_id: int) -> int:
        return len(self._characters.list_by_project(project_id))

    def _serialize_character(self, character) -> dict:
        if character is None:
            return {}
        thumbnail = self._serialize_asset(getattr(character, "thumbnail_asset_id", None) or getattr(character, "base_asset_id", None))
        return {
            "id": character.id,
            "name": character.name,
            "nickname": character.nickname,
            "thumbnail_asset": thumbnail,
        }

    def _serialize_asset(self, asset_id: int | None) -> dict | None:
        if not asset_id:
            return None
        asset = Asset.query.filter(Asset.id == asset_id, Asset.deleted_at.is_(None)).first()
        if not asset:
            return None
        return {
            "id": asset.id,
            "asset_type": asset.asset_type,
            "file_name": asset.file_name,
            "media_url": self._media_url(asset.file_path),
            "mime_type": asset.mime_type,
            "width": asset.width,
            "height": asset.height,
        }

    def _media_url(self, file_path: str | None):
        if not file_path:
            return None
        storage_root = current_app.config.get("STORAGE_ROOT")
        if not storage_root:
            return None
        normalized_path = os.path.normpath(file_path)
        normalized_root = os.path.normpath(storage_root)
        if not normalized_path.startswith(normalized_root):
            return None
        relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
        return f"/media/{relative}"

    def _generate_line_thread(
        self,
        *,
        project,
        participants: list,
        theme: str,
        min_turns: int,
        max_turns: int,
        exact_turns: bool,
        player_comment: str | None,
        plan: list[dict],
        conversation_history: list[dict] | None = None,
        long_term_memories: list[dict] | None = None,
        location_index: list[dict] | None = None,
        uploaded_image_observation: dict | None = None,
        participant_presence: dict | None = None,
    ) -> dict | None:
        world = self._worlds.get_world(project.id)
        length_rule = (
            f"Create exactly {max_turns} messages."
            if exact_turns
            else f"Create between {min_turns} and {max_turns} messages. End as soon as the joke lands naturally; do not pad to the maximum."
        )
        prompt = f"""
Return only JSON.
Create a LINE-style group chat thread for a Japanese character world app.
The player throws in a topic, then characters casually react like a real LINE group: short replies, teasing, quick corrections, and a few playful misunderstandings.

Required shape:
{{"title":"...", "theme":"...", "punchline":"...", "messages":[{{"turn":1, "speaker_id":1, "speaker_name":"...", "text":"..."}}]}}

Rules:
- Japanese only.
- {length_rule}
- Use only participant speaker_id values.
- Current room participants are all present in this LINE room and can read the conversation.
- Do not say a current participant is absent, not here, being talked about behind their back, or being praised "without me" unless that is explicitly about a past remembered event.
- If long-term memory says someone was absent in a past chat, treat that as past context only. In this generation, use the current participant presence list as truth.
- Characters may tease another current participant directly because they are in the room.
- Each message should be short, like LINE: 6-58 Japanese characters. One sharp joke is better than a long explanation.
- The manager plan decides turn order and rough function. Do not make characters announce or overperform their assigned role.
- Prioritize natural back-and-forth over formal structure. This is not a meeting, not a debate, and not a committee summary.
- Character personality should appear subtly through word choice and reaction speed. Do not force catchphrases, lore references, job titles, or self-introductions into every message.
- Every message must clearly respond to the previous 1-2 messages. If a character changes angle, bridge it with a phrase like "それで言うと", "いやそこじゃなくて", or "待って".
- Use boke/tsukkomi rhythm, but keep it conversational: one light misunderstanding, one quick correction, then move on.
- Use one recurring phrase as ten-don at most twice. Do not create multiple running jokes.
- The final 2-3 messages should pay off an earlier phrase, but stay short and casual.
- Keep it playful. Do not write explicit sexual content. If the theme is sensitive, convert it into comedy about boundaries, fashion, embarrassment, public reactions, or over-analysis.
- The player is not a participant inside messages unless player_comment is provided; if provided, characters should react to it in the first few turns.
- Do not narrate. Output chat messages only in JSON.
- Avoid calm explanations, generic agreement, safe committee summaries, and "結論は..." unless the line itself is the joke.
- Do not end with "仲良くしよう" style moralizing. End with a concrete funny line someone would screenshot.
- Avoid non-sequitur joke lines. Each message must respond to the previous message or move the current question forward.
- If a joke introduces a new object, explain why it is relevant within the same message or the next reply.
- At least every 5 turns, one character should casually pull the conversation back to the original topic.
- Use Recent room history as short-term memory. Characters may refer to prior jokes, promises, nicknames, misunderstandings, and relationships from it.
- Do not repeat the history verbatim. Continue from it naturally, and prioritize the player's new theme if history and theme compete.
- Use Long-term participant memories as durable memory. Characters can remember prior LINE room jokes, character-to-character relationships, nicknames, and unresolved topics.
- Long-term memories should influence word choice and callbacks lightly; do not dump them as exposition.
- Use World location index as shared light knowledge of the world: names, rough area, type, tags, owner, and one-line role.
- Facility knowledge has gradients: an owner can speak concretely about their own facility; non-owners should speak as visitors, by rumor, or with light uncertainty.
- Do not force facilities into the chat. Use them only when they naturally support the player's theme, a joke, a meetup idea, or a character callback.
- Do not invent detailed services, rooms, or rules for a facility unless the owner is speaking or the information is directly present in the location index.
- If Uploaded photo observation is present, characters should notice the photo and react to visible details from the observation.
- Do not claim to see details that are not in Uploaded photo observation. Ask or joke lightly if uncertain.

Project: {getattr(project, "title", "") or ""}
Project summary: {getattr(project, "summary", "") or ""}
World tone: {getattr(world, "tone", "") if world else ""}
World overview: {getattr(world, "overview", "") if world else ""}
Theme from player: {theme}
Player follow-up comment: {player_comment or ""}
Current participant presence: {json_util.dumps(participant_presence or {})}
Participants: {json_util.dumps([self._character_context(character) for character in participants])}
Recent room history: {json_util.dumps((conversation_history or [])[-40:])}
Long-term participant memories: {json_util.dumps(long_term_memories or [])}
World location index: {json_util.dumps(location_index or [])}
Uploaded photo observation: {json_util.dumps(uploaded_image_observation or {})}
Manager plan: {json_util.dumps(plan)}
Comedy beat menu: {json_util.dumps(COMEDY_BEATS)}
Story phases: {json_util.dumps(LINE_STORY_PHASES)}
""".strip()
        result = self._text_ai_client.generate_text(
            prompt,
            response_format={"type": "json_object"},
            temperature=0.9,
            max_tokens=2400,
        )
        parsed = self._text_ai_client._try_parse_json(result.get("text")) or {}
        messages = parsed.get("messages") if isinstance(parsed, dict) else []
        if not isinstance(messages, list) or not messages:
            return None
        normalized = self._normalize_messages(messages, participants=participants, max_turns=max_turns)
        if not normalized:
            return None
        if exact_turns and len(normalized) != max_turns:
            return None
        if not exact_turns and len(normalized) < min_turns:
            return None
        return {
            "project_id": project.id,
            "title": str(parsed.get("title") or "キャラクターLINE").strip(),
            "theme": theme,
            "player_comment": player_comment,
            "participant_ids": [character.id for character in participants],
            "manager_plan": plan,
            "messages": normalized,
            "punchline": str(parsed.get("punchline") or normalized[-1]["text"]).strip(),
        }

    def _fallback_thread(
        self,
        *,
        project_id: int,
        theme: str,
        turns: int,
        player_comment: str | None,
        participants: list,
        plan: list[dict],
        exact_turns: bool = False,
        conversation_history: list[dict] | None = None,
        long_term_memories: list[dict] | None = None,
        location_index: list[dict] | None = None,
        uploaded_image_observation: dict | None = None,
        participant_presence: dict | None = None,
    ) -> dict:
        messages = []
        templates = [
            "{theme}、初手の単語がもう強い。",
            "言い方で通知が一回ためらった気がする。",
            "でも本人が嫌がる方向には行かないでね。",
            "じゃあ『衣装の攻め具合』くらいに丸める？",
            "丸めたのに角が残ってるんだよ。",
            "待って、今の話はノア本人がどう感じるかが本題では。",
            "そこ大事。こっちだけで盛り上がると事故る。",
            "事故名だけ先に決めるなよ。『攻め具合事変』とか。",
            "その名前だけで怒られる自信ある。",
            "じゃあ本人に聞く。グループ名は今すぐ戻す。",
        ]
        for index in range(turns):
            character = participants[index % len(participants)]
            template = templates[index % len(templates)]
            text = template.format(theme=theme)
            if player_comment and index == 1:
                text = f"追撃『{player_comment}』来た。火力調整して。"
            if index == turns - 1:
                text = "本人に聞こう。あと『攻め具合事変』は消して。"
            messages.append(
                {
                    "turn": index + 1,
                    "speaker_id": character.id,
                    "speaker_name": character.name,
                    "text": text,
                    "role": plan[index % len(plan)]["role"] if plan else "",
                }
            )
        return {
            "project_id": project_id,
            "title": "キャラクターLINE",
            "theme": theme,
            "player_comment": player_comment,
            "participant_ids": [character.id for character in participants],
            "manager_plan": plan,
            "messages": messages,
            "punchline": messages[-1]["text"],
        }

    def _select_participants(self, characters: list, participant_count: int) -> list:
        count = max(2, min(int(participant_count or 8), min(len(characters), 12)))
        shuffled = list(characters)
        random.shuffle(shuffled)
        return shuffled[:count]

    def _build_manager_plan(self, participants: list, *, theme: str, turns: int) -> list[dict]:
        plan = []
        speaker_order = self._cycled_shuffle(participants, turns)
        role_order = self._cycled_shuffle(LINE_THREAD_PATTERNS, turns)
        for index in range(turns):
            character = speaker_order[index]
            role = role_order[index]
            if index == 0:
                role = "テーマ名に軽くツッコむ担当"
            elif index == 2:
                role = "本人不在で話す危うさを軽く止める担当"
            elif index == 5:
                role = "本題へ戻す担当"
            elif index >= turns - 3:
                role = "短くオチへ寄せる担当"
            plan.append(
                {
                    "turn": index + 1,
                    "speaker_id": character.id,
                    "speaker_name": character.name,
                    "role": role,
                    "topic_angle": self._topic_angle(theme, index),
                    "comedy_beat": COMEDY_BEATS[index % len(COMEDY_BEATS)],
                    "story_phase": LINE_STORY_PHASES[min(len(LINE_STORY_PHASES) - 1, int(index / max(1, turns - 1) * (len(LINE_STORY_PHASES) - 1)))],
                }
            )
        return plan

    def _topic_angle(self, theme: str, index: int) -> str:
        angles = [
            "テーマをそのまま拾う",
            "本人の尊厳や境界線に戻す",
            "恋愛や照れに誤読する",
            "都市や施設の反応に広げる",
            "具体物や写真映えの話に落とす",
            "誰かの口癖や弱点で脱線する",
            "最後のオチに向けて伏線を置く",
        ]
        return angles[index % len(angles)]

    def _normalize_messages(self, messages: list, *, participants: list, max_turns: int) -> list[dict]:
        by_id = {int(character.id): character for character in participants}
        fallback_order = self._cycled_shuffle(participants, max_turns)
        normalized = []
        for index, item in enumerate(messages[:max_turns]):
            if not isinstance(item, dict):
                continue
            try:
                speaker_id = int(item.get("speaker_id") or 0)
            except (TypeError, ValueError):
                speaker_id = 0
            character = by_id.get(speaker_id) or fallback_order[index]
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            normalized.append(
                {
                    "turn": len(normalized) + 1,
                    "speaker_id": character.id,
                    "speaker_name": character.name,
                    "text": text[:240],
                }
            )
        return normalized

    def _cycled_shuffle(self, values: list, count: int) -> list:
        if not values:
            return []
        result = []
        while len(result) < count:
            chunk = list(values)
            random.shuffle(chunk)
            result.extend(chunk)
        return result[:count]

    def _character_context(self, character) -> dict:
        if character is None:
            return {}
        return {
            "id": character.id,
            "name": character.name,
            "nickname": character.nickname,
            "gender": character.gender,
            "summary": character.character_summary,
            "personality": character.personality,
            "speech_style": character.speech_style,
            "speech_sample": character.speech_sample,
            "first_person": character.first_person,
            "ng_rules": character.ng_rules,
        }
