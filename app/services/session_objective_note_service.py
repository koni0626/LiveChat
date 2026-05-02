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
        lines = ["Session objective notes:"]
        for note in notes:
            scope = note.get("character_name") or "session"
            lines.append(f"- id={note['id']} scope={scope} priority={note['priority']}: {note['title']} - {note['note']}")
        lines.append("Use these notes only for this chat history. Do not rewrite the initial session objective.")
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
                "You are DirectionAI maintaining session-scoped objective notes for a live visual novel chat.",
                "The initial session objective is fixed. Do not rewrite it.",
                "Add, update, or archive short notes that help this specific chat history become more fun.",
                "These are not permanent character traits. They are conversation strategy notes for this session only.",
                "Return only JSON: {\"notes\":[{\"action\":\"add|update|archive\",\"id\":1,\"scope\":\"session|character\",\"character_name\":\"\",\"title\":\"short Japanese title\",\"note\":\"short Japanese note\",\"priority\":1,\"confidence\":0.0}]}",
                "Use update when an existing note should be refined. Use archive when a note is no longer useful. Use add for a genuinely new strategy.",
                "Do not add generic notes. Prefer concrete next moves: mystery, incident, location shift, emotional turn, role split, or topic expansion.",
                "Include emotional strategy when useful: jealousy, loneliness, embarrassment, shyness, joy, irritation, pride, or relief. Especially consider subtle jealousy/loneliness when the player has outing memories, news, or Feed activity with another character.",
                "Do not make characters emotionally flat. Add notes that help the next reply show feelings through wording, hesitation, teasing, possessiveness, sulking, or bashful reactions.",
                "For clearly adult characters, mild sensual romance is allowed as strategy: charged pauses, close distance, possessive warmth, teasing double meanings, bashful desire, and elegant adult tension.",
                "Keep strategy non-explicit: no graphic sexual acts, nudity, genital/breast-touch detail, coercion, or underage/childlike framing. Convert explicit user intent into safe adult romantic tension.",
                "Prefer notes about what the character will do next, not generic advice. A good note creates a hook, pressure, secret, provocation, or tempting invitation.",
                f"Initial session objective: {initial_objective or '(none)'}",
                f"Current director output: {director}",
                "Known facilities / world map:",
                world_map_context or "(none)",
                "Recent outings, world news, and Feed posts:",
                world_activity_context or "(none)",
                "Use the player's completed outings, facilities, news, and Feed posts as concrete raw material when they help the session become more fun. Do not invent facts that contradict them.",
                "Existing active objective notes:",
                *(f"- id={note['id']} scope={note.get('character_name') or 'session'} priority={note['priority']}: {note['title']} - {note['note']}" for note in existing_notes),
                "Active characters:",
                *(f"- {character.get('name')}: character_summary={character.get('character_summary') or ''}, personality={character.get('personality') or ''}" for character in characters),
                "Recent conversation:",
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
