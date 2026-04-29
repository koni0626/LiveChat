from __future__ import annotations

import random
import re

from ..repositories.story_roll_log_repository import StoryRollLogRepository
from ..utils import json_util


class StoryDiceService:
    FORMULA_RE = re.compile(r"^\s*(?P<count>\d*)d(?P<sides>\d+)\s*(?P<modifier>[+-]\s*\d+)?\s*$", re.IGNORECASE)

    def __init__(self, repository: StoryRollLogRepository | None = None):
        self._repo = repository or StoryRollLogRepository()

    def roll(
        self,
        session_id: int,
        formula: str,
        *,
        target: int | None = None,
        reason: str | None = None,
        message_id: int | None = None,
        metadata: dict | None = None,
    ):
        parsed = self.parse_formula(formula)
        dice = [
            {"sides": parsed["sides"], "result": random.randint(1, parsed["sides"])}
            for _ in range(parsed["count"])
        ]
        total = sum(item["result"] for item in dice) + parsed["modifier"]
        outcome = None
        if target is not None:
            outcome = "success" if total >= target else "failure"
        row = self._repo.create(
            {
                "session_id": session_id,
                "message_id": message_id,
                "formula": self.format_formula(parsed),
                "dice_json": json_util.dumps(dice),
                "modifier": parsed["modifier"],
                "total": total,
                "target": target,
                "outcome": outcome,
                "reason": reason,
                "metadata_json": json_util.dumps(metadata or {}),
            }
        )
        return self.serialize_roll(row)

    def parse_formula(self, formula: str):
        text = str(formula or "").strip().lower().replace(" ", "")
        match = self.FORMULA_RE.match(text)
        if not match:
            raise ValueError("dice formula is invalid")
        count = int(match.group("count") or 1)
        sides = int(match.group("sides") or 0)
        modifier_text = (match.group("modifier") or "").replace(" ", "")
        modifier = int(modifier_text) if modifier_text else 0
        if count <= 0 or count > 20:
            raise ValueError("dice count must be between 1 and 20")
        if sides not in {4, 6, 8, 10, 12, 20, 100}:
            raise ValueError("dice sides is not supported")
        return {"count": count, "sides": sides, "modifier": modifier}

    def format_formula(self, parsed: dict):
        base = f"{parsed['count']}d{parsed['sides']}"
        modifier = int(parsed.get("modifier") or 0)
        if modifier > 0:
            return f"{base}+{modifier}"
        if modifier < 0:
            return f"{base}{modifier}"
        return base

    def serialize_roll(self, row):
        if not row:
            return None
        return {
            "id": row.id,
            "session_id": row.session_id,
            "message_id": row.message_id,
            "formula": row.formula,
            "dice": json_util.loads(row.dice_json) if row.dice_json else [],
            "modifier": row.modifier,
            "total": row.total,
            "target": row.target,
            "outcome": row.outcome,
            "reason": row.reason,
            "metadata_json": json_util.loads(row.metadata_json) if row.metadata_json else {},
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
        }
