from __future__ import annotations

from datetime import datetime

from flask import current_app

from ..extensions import db
from ..models import CharacterMemoryNote


class CharacterMemoryNoteService:
    CATEGORIES = {
        "preference",
        "habit",
        "value",
        "weakness",
        "relationship",
        "foreshadowing",
        "fun_fact",
        "other",
    }

    def _normalize_category(self, value: str | None) -> str:
        category = str(value or "other").strip().lower()
        return category if category in self.CATEGORIES else "other"

    def _normalize_note(self, value: str | None) -> str:
        return str(value or "").strip()[:1000]

    def _normalize_confidence(self, value) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 1.0
        return max(0.0, min(1.0, confidence))

    def _normalized_for_duplicate(self, value: str | None) -> str:
        return "".join(str(value or "").lower().split())

    def get_note(self, note_id: int):
        return CharacterMemoryNote.query.get(note_id)

    def list_notes(self, character_id: int, *, include_disabled: bool = True, limit: int | None = None):
        query = CharacterMemoryNote.query.filter_by(character_id=character_id)
        if not include_disabled:
            query = query.filter_by(enabled=True)
        query = query.order_by(
            CharacterMemoryNote.pinned.desc(),
            CharacterMemoryNote.updated_at.desc(),
            CharacterMemoryNote.id.desc(),
        )
        if limit:
            query = query.limit(limit)
        return query.all()

    def serialize_note(self, row) -> dict:
        if not row:
            return {}
        return {
            "id": row.id,
            "character_id": row.character_id,
            "category": row.category,
            "note": row.note,
            "source_type": row.source_type,
            "source_ref": row.source_ref,
            "confidence": row.confidence,
            "enabled": bool(row.enabled),
            "pinned": bool(row.pinned),
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def list_serialized_notes(self, character_id: int, *, include_disabled: bool = True, limit: int | None = None):
        return [
            self.serialize_note(row)
            for row in self.list_notes(character_id, include_disabled=include_disabled, limit=limit)
        ]

    def has_duplicate(self, character_id: int, note: str, *, ignore_note_id: int | None = None) -> bool:
        target = self._normalized_for_duplicate(note)
        if not target:
            return False
        rows = CharacterMemoryNote.query.filter_by(character_id=character_id).all()
        for row in rows:
            if ignore_note_id and row.id == ignore_note_id:
                continue
            current = self._normalized_for_duplicate(row.note)
            if target == current or target in current or current in target:
                return True
        return False

    def create_note(self, character_id: int, payload: dict | None = None, *, source_type: str = "manual"):
        payload = dict(payload or {})
        note = self._normalize_note(payload.get("note"))
        if not note:
            raise ValueError("note is required")
        row = CharacterMemoryNote(
            character_id=character_id,
            category=self._normalize_category(payload.get("category")),
            note=note,
            source_type=str(payload.get("source_type") or source_type or "manual").strip()[:50],
            source_ref=str(payload.get("source_ref") or "").strip()[:255] or None,
            confidence=self._normalize_confidence(payload.get("confidence")),
            enabled=bool(payload.get("enabled", True)),
            pinned=bool(payload.get("pinned", False)),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def update_note(self, note_id: int, payload: dict | None = None):
        row = self.get_note(note_id)
        if not row:
            return None
        payload = dict(payload or {})
        if "category" in payload:
            row.category = self._normalize_category(payload.get("category"))
        if "note" in payload:
            note = self._normalize_note(payload.get("note"))
            if not note:
                raise ValueError("note is required")
            row.note = note
        if "confidence" in payload:
            row.confidence = self._normalize_confidence(payload.get("confidence"))
        if "enabled" in payload:
            row.enabled = bool(payload.get("enabled"))
        if "pinned" in payload:
            row.pinned = bool(payload.get("pinned"))
        row.updated_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row

    def delete_note(self, note_id: int) -> bool:
        row = self.get_note(note_id)
        if not row:
            return False
        db.session.delete(row)
        db.session.commit()
        return True

    def build_prompt_block(self, character_id: int, *, limit: int = 8) -> str:
        notes = self.list_notes(character_id, include_disabled=False, limit=limit)
        if not notes:
            return ""
        lines = [
            "Character growth notes:",
            *[f"- {row.category}: {row.note}" for row in notes],
            "Use these as additive characterization. Do not override the base profile or fixed character settings.",
        ]
        return "\n".join(lines)

    def extract_from_live_chat_context(self, text_ai_client, context: dict, *, source_ref: str | None = None) -> list[dict]:
        messages = context.get("messages") or []
        if len(messages) < 2:
            return []
        recent_lines = []
        for message in messages[-12:]:
            speaker = message.get("speaker_name") or message.get("sender_type") or ""
            text = str(message.get("message_text") or "").strip()
            if text:
                recent_lines.append(f"{speaker}: {text[:500]}")
        if not recent_lines:
            return []

        created = []
        for character in context.get("characters") or []:
            character_id = int(character.get("id") or 0)
            if not character_id:
                continue
            existing = self.build_prompt_block(character_id, limit=12)
            prompt = "\n".join(
                [
                    "You are maintaining additive character growth notes for a visual novel character.",
                    "Extract only notes that would make this character more interesting or more internally consistent later.",
                    "Good notes include preferences, habits, surprising tastes, values, vulnerabilities, relationship hooks, foreshadowing, or fun quirks.",
                    "Do not rewrite fixed base settings. Do not add generic summaries. Do not store private player profile facts here.",
                    "Return only JSON: {\"notes\":[{\"category\":\"preference|habit|value|weakness|relationship|foreshadowing|fun_fact|other\",\"note\":\"short Japanese note\",\"confidence\":0.0}]}",
                    f"Character: {character.get('name') or 'character'}",
                    f"Base personality: {character.get('personality') or ''}",
                    f"Speech style: {character.get('speech_style') or ''}",
                    f"Fixed memory notes: {character.get('memory_notes') or ''}",
                    f"Existing growth notes:\n{existing or '(none)'}",
                    "Recent conversation:",
                    *recent_lines,
                ]
            )
            try:
                result = text_ai_client.generate_text(
                    prompt,
                    temperature=0.2,
                    response_format={"type": "json_object"},
                    max_tokens=900,
                )
                parsed = text_ai_client._try_parse_json(result.get("text")) or {}
            except Exception as exc:
                try:
                    current_app.logger.info("character memory note extraction skipped: %s", exc)
                except RuntimeError:
                    pass
                continue
            for item in parsed.get("notes") or []:
                if not isinstance(item, dict):
                    continue
                note = self._normalize_note(item.get("note"))
                confidence = self._normalize_confidence(item.get("confidence"))
                if not note or confidence < 0.55 or self.has_duplicate(character_id, note):
                    continue
                row = self.create_note(
                    character_id,
                    {
                        "category": item.get("category"),
                        "note": note,
                        "confidence": confidence,
                        "enabled": True,
                        "source_ref": source_ref,
                    },
                    source_type="live_chat_ai",
                )
                created.append(self.serialize_note(row))
        return created
