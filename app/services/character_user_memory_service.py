from __future__ import annotations

from datetime import datetime

from ..extensions import db
from ..models import CharacterUserMemory


POSITIVE_AFFINITY_MARKERS = (
    "ありがとう",
    "好き",
    "大好き",
    "かわいい",
    "可愛い",
    "きれい",
    "綺麗",
    "素敵",
    "すごい",
    "会いたい",
    "一緒",
    "大切",
    "嬉しい",
    "楽しい",
    "似合う",
    "助かった",
    "信じて",
    "そばに",
)

STRONG_POSITIVE_AFFINITY_MARKERS = (
    "愛して",
    "惚れ",
    "抱きしめ",
    "キス",
    "守る",
    "君だけ",
    "お前だけ",
)

NEGATIVE_AFFINITY_MARKERS = (
    "嫌い",
    "うざい",
    "キモ",
    "きも",
    "黙れ",
    "最悪",
    "退屈",
    "つまら",
    "バカ",
    "馬鹿",
    "帰れ",
    "もういい",
    "やめろ",
)

STRONG_NEGATIVE_AFFINITY_MARKERS = (
    "二度と",
    "消えろ",
    "死ね",
    "怖い",
    "気持ち悪い",
    "触るな",
)


def _clamp_int(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, int(value)))


def affinity_label_for_score(score: int) -> str:
    score = _clamp_int(score, 0, 100)
    if score >= 85:
        return "恋慕"
    if score >= 70:
        return "強い好意"
    if score >= 55:
        return "親密"
    if score >= 40:
        return "親しみ"
    if score >= 20:
        return "様子見"
    return "警戒"


def physical_closeness_level_for_score(score: int) -> int:
    score = _clamp_int(score, 0, 100)
    if score >= 90:
        return 5
    if score >= 75:
        return 4
    if score >= 60:
        return 3
    if score >= 45:
        return 2
    if score >= 30:
        return 1
    return 0


def physical_closeness_label_for_level(level: int) -> str:
    labels = {
        0: "距離を保つ",
        1: "少し近づく",
        2: "隣に寄る",
        3: "軽い接触",
        4: "自発的な接触",
        5: "想いが重なる",
    }
    return labels.get(_clamp_int(level, 0, 5), labels[0])


class CharacterUserMemoryService:
    def get_memory(self, user_id: int, character_id: int):
        if not user_id or not character_id:
            return None
        return CharacterUserMemory.query.filter_by(user_id=user_id, character_id=character_id).first()

    def get_or_create_memory(self, user_id: int, character_id: int):
        row = self.get_memory(user_id, character_id)
        if row:
            return row
        row = CharacterUserMemory(user_id=user_id, character_id=character_id, memory_enabled=True)
        db.session.add(row)
        db.session.commit()
        return row

    def serialize_memory(self, row) -> dict:
        if not row:
            return {}
        return {
            "relationship_summary": row.relationship_summary or "",
            "memory_notes": row.memory_notes or "",
            "preference_notes": row.preference_notes or "",
            "unresolved_threads": row.unresolved_threads or "",
            "important_events": row.important_events or "",
            "affinity_score": _clamp_int(row.affinity_score or 0, 0, 100),
            "affinity_label": row.affinity_label or affinity_label_for_score(row.affinity_score or 0),
            "affinity_notes": row.affinity_notes or "",
            "physical_closeness_level": _clamp_int(row.physical_closeness_level or 0, 0, 5),
            "physical_closeness_label": physical_closeness_label_for_level(row.physical_closeness_level or 0),
            "last_interaction_at": row.last_interaction_at.isoformat() if row.last_interaction_at else None,
            "memory_enabled": bool(row.memory_enabled),
        }

    def build_prompt_block(self, user_id: int, character_id: int) -> str:
        row = self.get_memory(user_id, character_id)
        if not row or row.memory_enabled is False:
            return ""
        data = self.serialize_memory(row)
        lines = [
            "Character memory about this player:",
            f"relationship_summary: {data['relationship_summary'] or '(none)'}",
            f"shared_memories: {data['memory_notes'] or '(none)'}",
            f"player_preferences: {data['preference_notes'] or '(none)'}",
            f"open_threads: {data['unresolved_threads'] or '(none)'}",
            f"important_events: {data['important_events'] or '(none)'}",
            "Session affinity is managed separately per chat session. Use the current session affinity from context, not long-term memory, for warmth and physical closeness.",
            "Respect the character profile, NG rules, and explicit refusal. Do not force contact or make it graphically sexual.",
            "Use this memory subtly. Do not mention it unnaturally.",
        ]
        return "\n".join(lines)

    def _affinity_delta_from_exchange(self, user_text: str, character_text: str) -> tuple[int, str]:
        user_value = str(user_text or "")
        character_value = str(character_text or "")
        delta = 0
        reasons = []
        positive_hits = [marker for marker in POSITIVE_AFFINITY_MARKERS if marker in character_value]
        strong_positive_hits = [marker for marker in STRONG_POSITIVE_AFFINITY_MARKERS if marker in character_value]
        negative_hits = [marker for marker in NEGATIVE_AFFINITY_MARKERS if marker in character_value]
        strong_negative_hits = [marker for marker in STRONG_NEGATIVE_AFFINITY_MARKERS if marker in character_value]
        if positive_hits:
            delta += min(6, 2 + len(positive_hits))
            reasons.append("キャラの好意的な反応")
        if strong_positive_hits:
            delta += min(8, 4 + len(strong_positive_hits))
            reasons.append("キャラの強い親密表現")
        if negative_hits:
            delta -= min(8, 3 + len(negative_hits))
            reasons.append("キャラの否定的な反応")
        if strong_negative_hits:
            delta -= min(12, 6 + len(strong_negative_hits))
            reasons.append("キャラの強い拒絶")
        if not delta and character_value:
            delta = 1
            reasons.append("キャラが会話継続")
        if user_value and any(marker in user_value for marker in ("触るな", "やめて", "やめろ", "嫌だ", "いやだ")):
            delta = min(delta, -4)
            reasons.append("プレイヤーの拒否を尊重")
        return _clamp_int(delta, -15, 12), " / ".join(reasons)

    def update_affinity_from_exchange(
        self,
        *,
        user_id: int,
        character_id: int,
        user_text: str | None = None,
        character_text: str | None = None,
    ):
        row = self.get_or_create_memory(user_id, character_id)
        if row.memory_enabled is False:
            return row
        delta, reason = self._affinity_delta_from_exchange(user_text or "", character_text or "")
        current_score = _clamp_int(row.affinity_score or 0, 0, 100)
        next_score = _clamp_int(current_score + delta, 0, 100)
        row.affinity_score = next_score
        row.affinity_label = affinity_label_for_score(next_score)
        row.physical_closeness_level = physical_closeness_level_for_score(next_score)
        sign = "+" if delta >= 0 else ""
        row.affinity_notes = f"{datetime.utcnow().isoformat(timespec='seconds')}Z {sign}{delta}: {reason or '変化なし'}"[:1000]
        row.last_interaction_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row

    def update_affinity_from_ai_evaluation(
        self,
        *,
        user_id: int,
        character_id: int,
        affinity_delta: int = 0,
        reason: str | None = None,
        physical_closeness_delta: int = 0,
    ):
        row = self.get_or_create_memory(user_id, character_id)
        if row.memory_enabled is False:
            return row
        delta = _clamp_int(affinity_delta or 0, -12, 12)
        current_score = _clamp_int(row.affinity_score or 0, 0, 100)
        next_score = _clamp_int(current_score + delta, 0, 100)
        row.affinity_score = next_score
        row.affinity_label = affinity_label_for_score(next_score)
        base_level = physical_closeness_level_for_score(next_score)
        if physical_closeness_delta:
            base_level = _clamp_int(base_level + int(physical_closeness_delta), 0, 5)
        row.physical_closeness_level = base_level
        sign = "+" if delta >= 0 else ""
        note = str(reason or "AI好感度判定").strip()
        row.affinity_notes = f"{datetime.utcnow().isoformat(timespec='seconds')}Z {sign}{delta}: {note}"[:1000]
        row.last_interaction_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row

    def update_from_event(
        self,
        *,
        user_id: int,
        character_id: int,
        relationship_summary: str | None = None,
        memory_notes: str | None = None,
        preference_notes: str | None = None,
        unresolved_threads: str | None = None,
        important_events: str | None = None,
    ):
        row = self.get_or_create_memory(user_id, character_id)
        if row.memory_enabled is False:
            return row
        if relationship_summary:
            row.relationship_summary = str(relationship_summary).strip()[:1000]
        if memory_notes:
            row.memory_notes = str(memory_notes).strip()[:3000]
        if preference_notes:
            row.preference_notes = str(preference_notes).strip()[:2000]
        if unresolved_threads:
            row.unresolved_threads = str(unresolved_threads).strip()[:2000]
        if important_events:
            merged = "\n".join([item for item in [row.important_events, str(important_events).strip()] if item])
            row.important_events = merged[-4000:]
        row.last_interaction_at = datetime.utcnow()
        db.session.add(row)
        db.session.commit()
        return row
