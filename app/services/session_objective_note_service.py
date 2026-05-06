from __future__ import annotations

from datetime import datetime

from flask import current_app

from ..extensions import db
from ..models import ChatSessionObjectiveNote


class SessionObjectiveNoteService:
    ACTIVE_STATUS = "active"
    ARCHIVED_STATUS = "archived"

    def _normalize_text(self, value: str | None, limit: int) -> str:
        return str(value or "").strip()[:limit]

    def _normalize_priority(self, value) -> int:
        try:
            priority = int(value)
        except (TypeError, ValueError):
            priority = 3
        return max(1, min(5, priority))

    def _normalize_confidence(self, value) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 1.0
        return max(0.0, min(1.0, confidence))

    def _duplicate_key(self, value: str | None) -> str:
        return "".join(str(value or "").lower().split())

    def get_note(self, note_id: int):
        return ChatSessionObjectiveNote.query.get(note_id)

    def list_notes(self, session_id: int, *, include_archived: bool = False, limit: int | None = None):
        query = ChatSessionObjectiveNote.query.filter_by(session_id=session_id)
        if not include_archived:
            query = query.filter_by(status=self.ACTIVE_STATUS)
        query = query.order_by(
            ChatSessionObjectiveNote.priority.desc(),
            ChatSessionObjectiveNote.updated_at.desc(),
            ChatSessionObjectiveNote.id.desc(),
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def serialize_note(self, row, character_name_by_id: dict[int, str] | None = None) -> dict:
        if not row:
            return {}
        character_name_by_id = character_name_by_id or {}
        return {
            "id": row.id,
            "session_id": row.session_id,
            "character_id": row.character_id,
            "character_name": character_name_by_id.get(row.character_id) if row.character_id else None,
            "scope": "character" if row.character_id else "session",
            "title": row.title,
            "note": row.note,
            "priority": row.priority,
            "status": row.status,
            "source_type": row.source_type,
            "source_ref": row.source_ref,
            "confidence": row.confidence,
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def list_serialized_notes(
        self,
        session_id: int,
        *,
        characters: list[dict] | None = None,
        include_archived: bool = False,
        limit: int | None = None,
    ) -> list[dict]:
        character_name_by_id = {
            int(character.get("id")): character.get("name")
            for character in characters or []
            if character.get("id")
        }
        return [
            self.serialize_note(row, character_name_by_id)
            for row in self.list_notes(session_id, include_archived=include_archived, limit=limit)
        ]

    def has_duplicate(self, session_id: int, note: str) -> bool:
        target = self._duplicate_key(note)
        if not target:
            return False
        rows = ChatSessionObjectiveNote.query.filter_by(
            session_id=session_id,
            status=self.ACTIVE_STATUS,
        ).all()
        for row in rows:
            current = self._duplicate_key(row.note)
            if target == current or target in current or current in target:
                return True
        return False

    def create_note(
        self,
        session_id: int,
        payload: dict | None = None,
        *,
        source_type: str = "direction_ai",
    ):
        payload = dict(payload or {})
        title = self._normalize_text(payload.get("title"), 160)
        note = self._normalize_text(payload.get("note"), 1200)
        if not note:
            raise ValueError("note is required")
        if not title:
            title = note[:40]
        row = ChatSessionObjectiveNote(
            session_id=session_id,
            character_id=payload.get("character_id"),
            title=title,
            note=note,
            priority=self._normalize_priority(payload.get("priority")),
            status=self.ACTIVE_STATUS,
            source_type=self._normalize_text(payload.get("source_type") or source_type, 50),
            source_ref=self._normalize_text(payload.get("source_ref"), 255) or None,
            confidence=self._normalize_confidence(payload.get("confidence")),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def update_note(self, note_id: int, payload: dict | None = None):
        row = self.get_note(note_id)
        if not row:
            return None
        payload = dict(payload or {})
        if "title" in payload:
            row.title = self._normalize_text(payload.get("title"), 160) or row.title
        if "note" in payload:
            note = self._normalize_text(payload.get("note"), 1200)
            if note:
                row.note = note
        if "character_id" in payload:
            row.character_id = payload.get("character_id")
        if "priority" in payload:
            row.priority = self._normalize_priority(payload.get("priority"))
        if "confidence" in payload:
            row.confidence = self._normalize_confidence(payload.get("confidence"))
        if "status" in payload:
            status = self._normalize_text(payload.get("status"), 50)
            if status in {self.ACTIVE_STATUS, self.ARCHIVED_STATUS}:
                row.status = status
        row.updated_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row

    def build_prompt_block(self, session_id: int, *, characters: list[dict] | None = None, limit: int = 8) -> str:
        notes = self.list_serialized_notes(
            session_id,
            characters=characters,
            include_archived=False,
            limit=limit,
        )
        if not notes:
            return ""
        lines = ["セッション目的メモ:"]
        for note in notes:
            scope = note.get("character_name") or "session"
            lines.append(f"- id={note['id']} scope={scope} priority={note['priority']}: {note['title']} - {note['note']}")
        lines.append("これらのメモはこのチャット履歴の中だけで使ってください。初期セッション目的を書き換えないでください。")
        return "\n".join(lines)

    def update_from_direction(
        self,
        text_ai_client,
        context: dict,
        *,
        source_ref: str | None = None,
    ) -> list[dict]:
        session_id = int((context.get("session") or {}).get("id") or 0)
        if not session_id:
            return []
        messages = context.get("messages") or []
        if len(messages) < 2:
            return []

        characters = context.get("characters") or []
        character_id_by_name = {
            str(character.get("name") or "").strip(): int(character.get("id"))
            for character in characters
            if character.get("id") and character.get("name")
        }
        existing_notes = self.list_serialized_notes(session_id, characters=characters, include_archived=False, limit=12)
        director = ((context.get("state") or {}).get("state_json") or {}).get("conversation_director") or {}
        initial_objective = self._initial_objective(context)
        world_map_context = (context.get("world_map") or {}).get("prompt_context")
        world_activity_context = (context.get("world_activity") or {}).get("prompt_context")
        recent_lines = []
        for message in messages[-12:]:
            speaker = message.get("speaker_name") or message.get("sender_type") or ""
            text = self._normalize_text(message.get("message_text"), 500)
            if text:
                recent_lines.append(f"{speaker}: {text}")

        prompt = "\n".join(
            [
                "ライブ形式のビジュアルノベルチャット向けに、セッション内だけで使う目的メモを管理してください。",
                "初期セッション目的は固定です。書き換えないでください。",
                "この特定のチャット履歴がもっと面白くなる短いメモを、追加・更新・アーカイブしてください。",
                "これは恒久的なキャラクター特性ではありません。このセッションだけの会話戦略メモです。",
                "JSONのみを返してください: {\"notes\":[{\"action\":\"add|update|archive\",\"id\":1,\"scope\":\"session|character\",\"character_name\":\"\",\"title\":\"短い日本語タイトル\",\"note\":\"短い日本語メモ\",\"priority\":1,\"confidence\":0.0}]}",
                "既存メモを洗練する場合は update、不要になったメモは archive、本当に新しい戦略は add を使ってください。",
                "汎用的なメモは追加しないでください。謎、事件、場所移動、感情の転換、役割分担、話題拡張など、具体的な次の動きを優先してください。",
                "有用な場合は感情戦略を含めてください。嫉妬、寂しさ、照れ、恥じらい、喜び、苛立ち、誇り、安堵など。特に、プレイヤーが他キャラクターとのおでかけ記憶、ニュース、Feed活動を持つ場合は、さりげない嫉妬や寂しさを検討してください。",
                "キャラクターを感情的に平坦にしないでください。次の返答が、言葉選び、ためらい、からかい、独占欲、拗ね、照れ反応などで感情を見せやすくなるメモを追加してください。",
                "明確に成人のキャラクターなら、戦略として軽い官能的な恋愛感は許可されます。含みのある間、近い距離、独占的な温かさ、からかう二重の意味、照れた欲求、上品な大人の緊張感などです。",
                "戦略は非露骨にしてください。露骨な性行為、裸体、局部/胸への接触詳細、強制、未成年/幼く見える構図は禁止です。露骨なユーザー意図は、安全な大人の恋愛的緊張へ変換してください。",
                "汎用アドバイスではなく、キャラクターが次に何をするかのメモを優先してください。良いメモは、フック、圧、秘密、挑発、魅力的な誘いを作ります。",
                f"初期セッション目的: {initial_objective or '(なし)'}",
                f"現在のディレクター出力: {director}",
                "既知の施設/ワールドマップ:",
                world_map_context or "(なし)",
                "最近のおでかけ、ワールドニュース、Feed投稿:",
                world_activity_context or "(なし)",
                "プレイヤーの完了済みおでかけ、施設、ニュース、Feed投稿は、セッションを面白くする助けになる場合だけ具体的な素材として使ってください。矛盾する事実を創作しないでください。",
                "既存の有効な目的メモ:",
                *(f"- id={note['id']} scope={note.get('character_name') or 'session'} priority={note['priority']}: {note['title']} - {note['note']}" for note in existing_notes),
                "登場中キャラクター:",
                *(f"- {character.get('name')}: character_summary={character.get('character_summary') or ''}, personality={character.get('personality') or ''}" for character in characters),
                "直近の会話:",
                *recent_lines,
            ]
        )
        try:
            result = text_ai_client.generate_text(
                prompt,
                temperature=0.25,
                response_format={"type": "json_object"},
                max_tokens=1200,
            )
            parsed = text_ai_client._try_parse_json(result.get("text")) or {}
        except Exception as exc:
            try:
                current_app.logger.info("session objective note update skipped: %s", exc)
            except RuntimeError:
                pass
            return []

        changed = []
        for item in parsed.get("notes") or []:
            if not isinstance(item, dict):
                continue
            action = self._normalize_text(item.get("action"), 20).lower()
            confidence = self._normalize_confidence(item.get("confidence"))
            if confidence < 0.5:
                continue
            note_id = item.get("id")
            character_id = None
            if self._normalize_text(item.get("scope"), 20) == "character":
                character_id = character_id_by_name.get(self._normalize_text(item.get("character_name"), 160))
            payload = {
                "title": item.get("title"),
                "note": item.get("note"),
                "priority": item.get("priority"),
                "confidence": confidence,
                "character_id": character_id,
                "source_ref": source_ref,
            }
            try:
                if action == "archive" and note_id:
                    row = self.get_note(int(note_id))
                    if row and row.session_id == session_id:
                        row = self.update_note(row.id, {"status": self.ARCHIVED_STATUS, "confidence": confidence})
                        changed.append(self.serialize_note(row))
                elif action == "update" and note_id:
                    row = self.get_note(int(note_id))
                    if row and row.session_id == session_id:
                        row = self.update_note(row.id, payload)
                        changed.append(self.serialize_note(row))
                elif action == "add":
                    note_text = self._normalize_text(item.get("note"), 1200)
                    if note_text and not self.has_duplicate(session_id, note_text):
                        row = self.create_note(
                            session_id,
                            payload,
                            source_type="direction_ai",
                        )
                        changed.append(self.serialize_note(row))
            except Exception as exc:
                try:
                    current_app.logger.info("session objective note item skipped: %s", exc)
                except RuntimeError:
                    pass
        return changed

    def _initial_objective(self, context: dict) -> str:
        session = context.get("session") or {}
        room_snapshot = session.get("room_snapshot_json") or {}
        if isinstance(room_snapshot, dict) and room_snapshot.get("conversation_objective"):
            return self._normalize_text(room_snapshot.get("conversation_objective"), 1200)
        room = context.get("room") or {}
        if isinstance(room, dict) and room.get("conversation_objective"):
            return self._normalize_text(room.get("conversation_objective"), 1200)
        settings = session.get("settings_json") or {}
        if isinstance(settings, dict):
            return self._normalize_text(settings.get("conversation_objective") or settings.get("session_objective"), 1200)
        return ""
