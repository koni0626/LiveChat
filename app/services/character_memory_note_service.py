from __future__ import annotations

from datetime import datetime

from flask import current_app

from ..extensions import db
from ..models import CharacterMemoryNote, CharacterMemorySummary
from ..utils import json_util


class CharacterMemoryNoteService:
    SUMMARY_REFRESH_NOTE_THRESHOLD = 8
    SUMMARY_REFRESH_HOURS = 24

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

    def list_notes(
        self,
        user_id: int,
        character_id: int,
        *,
        include_disabled: bool = True,
        limit: int | None = None,
    ):
        query = CharacterMemoryNote.query.filter_by(user_id=user_id, character_id=character_id)
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
            "user_id": row.user_id,
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

    def _load_json(self, value):
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json_util.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def get_summary(self, user_id: int, character_id: int):
        return CharacterMemorySummary.query.filter_by(user_id=user_id, character_id=character_id).first()

    def serialize_summary(self, row) -> dict:
        if not row:
            return {
                "summary_json": {},
                "prompt_text": "",
                "source_note_count": 0,
                "source_note_max_id": 0,
                "created_at": None,
                "updated_at": None,
            }
        return {
            "id": row.id,
            "user_id": row.user_id,
            "character_id": row.character_id,
            "summary_json": self._load_json(row.summary_json),
            "prompt_text": row.prompt_text or "",
            "source_note_count": row.source_note_count,
            "source_note_max_id": row.source_note_max_id,
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def list_serialized_notes(
        self,
        user_id: int,
        character_id: int,
        *,
        include_disabled: bool = True,
        limit: int | None = None,
    ):
        return [
            self.serialize_note(row)
            for row in self.list_notes(user_id, character_id, include_disabled=include_disabled, limit=limit)
        ]

    def has_duplicate(
        self,
        user_id: int,
        character_id: int,
        note: str,
        *,
        ignore_note_id: int | None = None,
    ) -> bool:
        target = self._normalized_for_duplicate(note)
        if not target:
            return False
        rows = CharacterMemoryNote.query.filter_by(user_id=user_id, character_id=character_id).all()
        for row in rows:
            if ignore_note_id and row.id == ignore_note_id:
                continue
            current = self._normalized_for_duplicate(row.note)
            if target == current or target in current or current in target:
                return True
        return False

    def create_note(
        self,
        user_id: int,
        character_id: int,
        payload: dict | None = None,
        *,
        source_type: str = "manual",
    ):
        payload = dict(payload or {})
        note = self._normalize_note(payload.get("note"))
        if not note:
            raise ValueError("note is required")
        row = CharacterMemoryNote(
            user_id=user_id,
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

    def build_prompt_block(self, user_id: int, character_id: int, *, limit: int = 8) -> str:
        summary = self.get_summary(user_id, character_id)
        if summary and str(summary.prompt_text or "").strip():
            return "\n".join(
                [
                    "Character growth summary:",
                    str(summary.prompt_text).strip(),
                    "Use this as additive characterization. Do not override the base profile or fixed character settings.",
                ]
            )
        notes = self.list_notes(user_id, character_id, include_disabled=False, limit=limit)
        if not notes:
            return ""
        lines = [
            "Character growth notes:",
            *[f"- {row.category}: {row.note}" for row in notes],
            "Use these as additive characterization. Do not override the base profile or fixed character settings.",
        ]
        return "\n".join(lines)

    def summarize_notes(
        self,
        text_ai_client,
        user_id: int,
        character: dict,
        *,
        force: bool = False,
    ) -> dict:
        character_id = int(character.get("id") or 0)
        if not user_id or not character_id:
            return self.serialize_summary(None)
        notes = self.list_notes(user_id, character_id, include_disabled=False)
        existing = self.get_summary(user_id, character_id)
        max_note_id = max((int(note.id or 0) for note in notes), default=0)
        note_count = len(notes)
        previous_max_id = int(getattr(existing, "source_note_max_id", 0) or 0)
        new_note_count = len([note for note in notes if int(note.id or 0) > previous_max_id])
        stale = False
        if existing and getattr(existing, "updated_at", None):
            stale = (datetime.utcnow() - existing.updated_at).total_seconds() >= self.SUMMARY_REFRESH_HOURS * 3600
        if not force and existing and new_note_count < self.SUMMARY_REFRESH_NOTE_THRESHOLD and not (stale and new_note_count):
            return self.serialize_summary(existing)
        if not notes:
            return self._upsert_summary(user_id, character_id, {}, "", 0, 0)

        source_notes = notes[:80]
        existing_summary = self._load_json(getattr(existing, "summary_json", None))
        prompt = "\n".join(
            [
                "日本語で、キャラクターのAIメモを会話用の短い成長要約に統合してください。",
                "個別メモを羅列せず、重複や近い意味をまとめてください。",
                "出力はJSONのみ。",
                "必須キー: overview, stable_traits, habits, preferences, relationship_hooks, boundaries, open_threads, prompt_text",
                "stable_traits, habits, preferences, relationship_hooks, boundaries, open_threads は短い日本語文字列の配列にしてください。",
                "prompt_text はライブチャットのプロンプトにそのまま入れる300〜700字程度の日本語要約にしてください。",
                "固定のキャラ設定を上書きせず、会話で増えた追加情報だけにしてください。",
                f"キャラクター名: {character.get('name') or 'character'}",
                f"キャラクター概要: {character.get('character_summary') or ''}",
                f"基本性格: {character.get('personality') or ''}",
                f"話し方: {character.get('speech_style') or ''}",
                f"既存要約: {json_util.dumps(existing_summary) if existing_summary else '{}'}",
                "AIメモ:",
                *[f"- {note.category}: {note.note}" for note in source_notes],
            ]
        )
        try:
            result = text_ai_client.generate_text(
                prompt,
                temperature=0.2,
                response_format={"type": "json_object"},
                max_tokens=1400,
            )
            parsed = text_ai_client._try_parse_json(result.get("text")) or {}
            if not isinstance(parsed, dict):
                parsed = {}
        except Exception as exc:
            try:
                current_app.logger.info("character memory summary skipped: %s", exc)
            except RuntimeError:
                pass
            if not existing:
                normalized = self._normalize_summary({}, notes[:8])
                return self._upsert_summary(
                    user_id,
                    character_id,
                    normalized,
                    normalized.get("prompt_text") or "",
                    note_count,
                    max_note_id,
                )
            return self.serialize_summary(existing)
        normalized = self._normalize_summary(parsed, source_notes)
        return self._upsert_summary(
            user_id,
            character_id,
            normalized,
            normalized.get("prompt_text") or "",
            note_count,
            max_note_id,
        )

    def summarize_if_needed(self, text_ai_client, user_id: int, character: dict) -> dict:
        return self.summarize_notes(text_ai_client, user_id, character, force=False)

    def _normalize_summary(self, parsed: dict, notes) -> dict:
        def text(value, max_len=1000):
            return str(value or "").strip()[:max_len]

        def text_list(value, limit=8):
            if not isinstance(value, list):
                return []
            return [text(item, 220) for item in value if text(item, 220)][:limit]

        fallback_prompt = "\n".join(f"- {note.category}: {note.note}" for note in notes[:8])
        prompt_text = text(parsed.get("prompt_text"), 1400) or fallback_prompt
        return {
            "overview": text(parsed.get("overview"), 600),
            "stable_traits": text_list(parsed.get("stable_traits")),
            "habits": text_list(parsed.get("habits")),
            "preferences": text_list(parsed.get("preferences")),
            "relationship_hooks": text_list(parsed.get("relationship_hooks")),
            "boundaries": text_list(parsed.get("boundaries")),
            "open_threads": text_list(parsed.get("open_threads")),
            "prompt_text": prompt_text,
        }

    def _upsert_summary(
        self,
        user_id: int,
        character_id: int,
        summary_json: dict,
        prompt_text: str,
        source_note_count: int,
        source_note_max_id: int,
    ) -> dict:
        row = self.get_summary(user_id, character_id)
        if not row:
            row = CharacterMemorySummary(user_id=user_id, character_id=character_id)
        row.summary_json = json_util.dumps(summary_json)
        row.prompt_text = str(prompt_text or "").strip()
        row.source_note_count = int(source_note_count or 0)
        row.source_note_max_id = int(source_note_max_id or 0)
        row.updated_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return self.serialize_summary(row)

    def extract_from_live_chat_context(self, text_ai_client, context: dict, *, source_ref: str | None = None) -> list[dict]:
        messages = context.get("messages") or []
        if len(messages) < 2:
            return []
        session = context.get("session") or {}
        user_id = int(session.get("owner_user_id") or 0)
        if not user_id:
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
            existing = self.build_prompt_block(user_id, character_id, limit=12)
            prompt = "\n".join(
                [
                    "You are maintaining additive character growth notes for a visual novel character.",
                    "Extract only notes that would make this character more interesting or more internally consistent later.",
                    "Good notes include preferences, habits, surprising tastes, values, vulnerabilities, relationship hooks, foreshadowing, or fun quirks.",
                    "Do not rewrite fixed base settings. Do not add generic summaries. Do not store private player profile facts here.",
                    "Return only JSON: {\"notes\":[{\"category\":\"preference|habit|value|weakness|relationship|foreshadowing|fun_fact|other\",\"note\":\"short Japanese note\",\"confidence\":0.0}]}",
                    f"Character: {character.get('name') or 'character'}",
                    f"Character overview: {character.get('character_summary') or ''}",
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
                if not note or confidence < 0.55 or self.has_duplicate(user_id, character_id, note):
                    continue
                row = self.create_note(
                    user_id,
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
            if created:
                self.summarize_if_needed(text_ai_client, user_id, character)
        return created
