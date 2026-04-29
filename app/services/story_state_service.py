from __future__ import annotations

from copy import deepcopy

from ..repositories.story_session_state_repository import StorySessionStateRepository
from ..utils import json_util


class StoryStateService:
    def __init__(self, repository: StorySessionStateRepository | None = None):
        self._repo = repository or StorySessionStateRepository()

    def load_json(self, value, fallback=None):
        if value is None:
            return deepcopy(fallback) if fallback is not None else {}
        if isinstance(value, (dict, list)):
            return deepcopy(value)
        text = str(value or "").strip()
        if not text:
            return deepcopy(fallback) if fallback is not None else {}
        try:
            parsed = json_util.loads(text)
        except Exception:
            return deepcopy(fallback) if fallback is not None else {}
        return parsed if parsed is not None else (deepcopy(fallback) if fallback is not None else {})

    def default_state(self, story_mode: str | None = None):
        return {
            "game_state": {
                "mode": story_mode or "free_chat",
                "location": "",
                "progress": 0,
                "danger": 0,
                "inventory": [],
                "flags": [],
                "open_threads": [],
            },
            "relationship_state": {
                "affection": 10,
                "trust": 10,
                "tension": 0,
                "romance_stage": 0,
            },
            "event_state": {
                "turn_count": 0,
                "last_event_turn": 0,
                "used_events": [],
                "pending_event": None,
            },
            "choice_state": {
                "last_choices": [],
                "policy": "explore_romance_risk",
            },
            "goal_state": {
                "main_goal": "",
                "current_goal": "",
                "max_turns": 10,
                "current_turn": 0,
                "current_phase": "opening",
                "current_phase_label": "導入・目的提示",
                "clear_conditions": [],
                "completed_goals": [],
                "session_status": "active",
            },
            "visual_state": {
                "active_visual_type": "location",
                "active_subject": "",
            },
        }

    def get_state(self, session_id: int):
        return self._repo.get_by_session(session_id)

    def serialize_state(self, row):
        if not row:
            return None
        return {
            "id": row.id,
            "session_id": row.session_id,
            "state_json": self.load_json(row.state_json),
            "version": row.version,
            "created_at": row.created_at.isoformat() if getattr(row, "created_at", None) else None,
            "updated_at": row.updated_at.isoformat() if getattr(row, "updated_at", None) else None,
        }

    def initialize_state(self, session_id: int, state: dict):
        return self._repo.upsert(session_id, {"state_json": json_util.dumps(state), "version": 1})

    def upsert_state(self, session_id: int, state: dict):
        return self._repo.upsert(session_id, {"state_json": json_util.dumps(state)})

    def apply_patch(self, session_id: int, patch: dict | None):
        row = self.get_state(session_id)
        state = self.load_json(row.state_json if row else None, fallback=self.default_state())
        patch = patch if isinstance(patch, dict) else {}

        self._apply_game_state(state, patch.get("game_state") or {})
        self._apply_relationship_state(state, patch.get("relationship_state") or {})
        self._apply_inventory_patch(state, patch.get("inventory") or {})
        self._apply_visual_state(state, patch.get("visual_state") or {})
        self._apply_choice_state(state, patch.get("choice_state") or {})
        self._apply_event_state(state, patch.get("event_state") or {})
        self._apply_goal_state(state, patch.get("goal_state") or {})

        return self.upsert_state(session_id, state)

    def _bounded_delta(self, current, delta, *, minimum=0, maximum=100, max_abs_delta=20):
        try:
            current_value = int(current or 0)
        except (TypeError, ValueError):
            current_value = 0
        try:
            delta_value = int(delta or 0)
        except (TypeError, ValueError):
            delta_value = 0
        delta_value = max(-max_abs_delta, min(max_abs_delta, delta_value))
        return max(minimum, min(maximum, current_value + delta_value))

    def _apply_game_state(self, state: dict, patch: dict):
        game_state = state.setdefault("game_state", {})
        for key in ("mode", "location"):
            if key in patch:
                game_state[key] = str(patch.get(key) or "").strip()
        for key in ("progress", "danger"):
            delta_key = f"{key}_delta"
            if delta_key in patch:
                game_state[key] = self._bounded_delta(game_state.get(key), patch.get(delta_key))
            elif key in patch:
                game_state[key] = self._bounded_delta(0, patch.get(key), max_abs_delta=100)
        for key in ("flags", "open_threads"):
            additions = patch.get(f"{key}_add")
            if isinstance(additions, list):
                values = list(game_state.get(key) or [])
                for item in additions:
                    text = str(item or "").strip()
                    if text and text not in values:
                        values.append(text)
                game_state[key] = values[:50]

    def _apply_relationship_state(self, state: dict, patch: dict):
        relationship = state.setdefault("relationship_state", {})
        field_map = {
            "affection_delta": "affection",
            "trust_delta": "trust",
            "tension_delta": "tension",
            "romance_stage_delta": "romance_stage",
        }
        for source, target in field_map.items():
            if source in patch:
                max_value = 5 if target == "romance_stage" else 100
                relationship[target] = self._bounded_delta(relationship.get(target), patch.get(source), maximum=max_value)

    def _apply_inventory_patch(self, state: dict, patch: dict):
        if not isinstance(patch, dict):
            return
        game_state = state.setdefault("game_state", {})
        inventory = list(game_state.get("inventory") or [])
        known_ids = {str(item.get("id")) for item in inventory if isinstance(item, dict) and item.get("id")}
        for item in patch.get("add") or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("id") or "").strip()
            name = str(item.get("name") or "").strip()
            if not item_id or not name or item_id in known_ids:
                continue
            inventory.append(
                {
                    "id": item_id,
                    "name": name,
                    "type": str(item.get("type") or "item").strip() or "item",
                    "owner": str(item.get("owner") or "player").strip() or "player",
                    "equipped": bool(item.get("equipped")),
                    "visible": bool(item.get("visible")),
                    "visual_description": str(item.get("visual_description") or "").strip(),
                    "visibility_priority": int(item.get("visibility_priority") or 0),
                }
            )
            known_ids.add(item_id)
        game_state["inventory"] = inventory[:100]

    def _apply_visual_state(self, state: dict, patch: dict):
        if isinstance(patch, dict):
            visual_state = state.setdefault("visual_state", {})
            for key, value in patch.items():
                if key in {"active_visual_type", "active_subject", "character_visible_items"}:
                    visual_state[key] = value

    def _apply_choice_state(self, state: dict, patch: dict):
        if isinstance(patch, dict):
            choice_state = state.setdefault("choice_state", {})
            if "last_choices" in patch and isinstance(patch["last_choices"], list):
                choice_state["last_choices"] = patch["last_choices"][:3]
            if "policy" in patch:
                choice_state["policy"] = str(patch.get("policy") or "").strip()

    def _apply_event_state(self, state: dict, patch: dict):
        if isinstance(patch, dict):
            event_state = state.setdefault("event_state", {})
            if "pending_event" in patch:
                event_state["pending_event"] = patch.get("pending_event")
            if "last_event_turn" in patch:
                event_state["last_event_turn"] = self._bounded_delta(
                    0,
                    patch.get("last_event_turn"),
                    maximum=100000,
                    max_abs_delta=100000,
                )
            if "used_events_add" in patch and isinstance(patch["used_events_add"], list):
                used_events = list(event_state.get("used_events") or [])
                for item in patch["used_events_add"]:
                    text = str(item or "").strip()
                    if text and text not in used_events:
                        used_events.append(text)
                event_state["used_events"] = used_events[:100]
            if "turn_count_delta" in patch:
                event_state["turn_count"] = self._bounded_delta(
                    event_state.get("turn_count"),
                    patch.get("turn_count_delta"),
                    maximum=100000,
                    max_abs_delta=100,
                )

    def _apply_goal_state(self, state: dict, patch: dict):
        if not isinstance(patch, dict):
            return
        goal_state = state.setdefault("goal_state", {})
        for key in ("main_goal", "current_goal", "current_phase", "current_phase_label", "session_status"):
            if key in patch:
                goal_state[key] = str(patch.get(key) or "").strip()
        for key in ("max_turns", "current_turn"):
            if key in patch:
                goal_state[key] = self._bounded_delta(
                    0,
                    patch.get(key),
                    maximum=100000,
                    max_abs_delta=100000,
                )
        for key in ("clear_conditions", "completed_goals"):
            if key in patch and isinstance(patch[key], list):
                values = []
                for item in patch[key]:
                    text = str(item or "").strip()
                    if text and text not in values:
                        values.append(text)
                goal_state[key] = values[:20]
