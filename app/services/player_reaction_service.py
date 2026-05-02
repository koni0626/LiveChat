from __future__ import annotations

import os
import tempfile
from datetime import datetime

from ..clients.text_ai_client import TextAIClient
from ..utils import json_util
from .session_state_service import SessionStateService


class PlayerReactionService:
    MOODS = {"amused", "engaged", "neutral", "confused", "uncomfortable", "unknown"}
    ENGAGEMENTS = {"high", "medium", "low", "unknown"}

    def __init__(
        self,
        *,
        text_ai_client: TextAIClient | None = None,
        session_state_service: SessionStateService | None = None,
    ):
        self._text_ai_client = text_ai_client or TextAIClient()
        self._session_state_service = session_state_service or SessionStateService()

    def _load_state_json(self, session_id: int) -> dict:
        row = self._session_state_service.get_state(session_id)
        if not row or not getattr(row, "state_json", None):
            return {}
        try:
            parsed = json_util.loads(row.state_json)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}

    def _normalize_reaction(self, payload: dict | None) -> dict:
        payload = dict(payload or {})
        mood = str(payload.get("mood") or "unknown").strip().lower()
        engagement = str(payload.get("engagement") or "unknown").strip().lower()
        try:
            confidence = float(payload.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.0
        return {
            "mood": mood if mood in self.MOODS else "unknown",
            "engagement": engagement if engagement in self.ENGAGEMENTS else "unknown",
            "confidence": max(0.0, min(1.0, confidence)),
            "short_note": str(payload.get("short_note") or "").strip()[:240],
            "captured_at": datetime.utcnow().isoformat(),
        }

    def analyze_frame(self, session_id: int, upload_file) -> dict:
        if upload_file is None:
            raise ValueError("file is required")
        suffix = ".jpg"
        filename = str(getattr(upload_file, "filename", "") or "").lower()
        if filename.endswith(".png"):
            suffix = ".png"
        elif filename.endswith(".webp"):
            suffix = ".webp"

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_path = temp_file.name
                upload_file.save(temp_file)
            prompt = (
                "Return only JSON. Analyze the visible player's current apparent reaction in this webcam frame. "
                "Do not identify the person. Do not infer age, gender, ethnicity, identity, health, or other sensitive traits. "
                "Use cautious wording and only describe apparent expression/engagement. "
                "Required keys: mood, engagement, confidence, short_note. "
                "mood must be one of amused, engaged, neutral, confused, uncomfortable, unknown. "
                "engagement must be one of high, medium, low, unknown. "
                "confidence must be a number from 0 to 1. "
                "Be sensitive to subtle but visible cues. "
                "Use amused for even a slight smile, softened eyes, raised cheeks, or a playful expression. "
                "Use engaged for direct attention, leaning toward the screen, bright eyes, or an interested look even without a big smile. "
                "Use confused for tilted head, furrowed brow, narrowed eyes, or a searching/unsure look. "
                "Use uncomfortable for visible tension, avoidance, grimace, or strained expression. "
                "Use neutral only when there are no meaningful visible cues beyond a calm resting face. "
                "Do not default to neutral just because the expression is subtle. "
                "short_note must be one short natural Japanese sentence, for example '少し笑っているように見える。', "
                "'画面に集中しているように見える。', or '少し迷っているように見える。'."
            )
            result = self._text_ai_client.analyze_image(
                temp_path,
                prompt=prompt,
            )
            reaction = self._normalize_reaction(result.get("parsed_json") or {})
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

        state_json = self._load_state_json(session_id)
        state_json["player_visible_reaction"] = reaction
        self._session_state_service.upsert_state(session_id, {"state_json": state_json})
        return reaction
