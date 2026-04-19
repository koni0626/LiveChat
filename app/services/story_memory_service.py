import re

from ..repositories.story_memory_repository import StoryMemoryRepository
from ..utils import json_util


class StoryMemoryService:
    PLAYER_NAME_KEYS = ("player_name", "protagonist_name", "user_name")
    IMPORTANT_KEYWORDS = ("名前", "呼", "約束", "目的", "秘密", "鍵", "条件", "真相", "ルール", "敵", "味方")

    def __init__(self, repository: StoryMemoryRepository | None = None):
        self._repo = repository or StoryMemoryRepository()

    def _load_json(self, value):
        if value is None or isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            return None
        try:
            return json_util.loads(text)
        except Exception:
            return value

    def _shorten(self, value: str | None, length: int = 180) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text if len(text) <= length else text[: length - 1] + "..."

    def _collect_dialogue_lines(self, scene) -> list[str]:
        dialogues = self._load_json(getattr(scene, "dialogue_json", None))
        if not isinstance(dialogues, list):
            return []
        lines = []
        for item in dialogues:
            if not isinstance(item, dict):
                continue
            speaker = str(item.get("speaker") or "").strip()
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            lines.append(f"{speaker}: {text}" if speaker else text)
        return lines

    def _extract_player_name(self, scene):
        state = self._load_json(getattr(scene, "scene_state_json", None))
        if isinstance(state, dict):
            for key in self.PLAYER_NAME_KEYS:
                value = state.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            player = state.get("player")
            if isinstance(player, dict):
                name = player.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()

        combined = "\n".join(
            filter(
                None,
                [
                    getattr(scene, "summary", None),
                    getattr(scene, "narration_text", None),
                    *self._collect_dialogue_lines(scene),
                ],
            )
        )
        match = re.search(r"(?:名前は|名は|あなたは)([^\s、。]{1,20})", combined)
        if match:
            return match.group(1).strip()
        return None

    def _build_scene_digest(self, scene):
        parts = []
        title = self._shorten(getattr(scene, "title", None), 60)
        summary = self._shorten(getattr(scene, "summary", None), 100)
        narration = self._shorten(getattr(scene, "narration_text", None), 140)
        dialogue_lines = self._collect_dialogue_lines(scene)[:2]
        if title:
            parts.append(f"title={title}")
        if summary:
            parts.append(f"summary={summary}")
        if narration:
            parts.append(f"narration={narration}")
        if dialogue_lines:
            parts.append("dialogue=" + " / ".join(dialogue_lines))
        return " | ".join(parts) if parts else None

    def _build_important_note(self, scene):
        candidates = []
        summary = self._shorten(getattr(scene, "summary", None), 120)
        narration = self._shorten(getattr(scene, "narration_text", None), 180)
        if summary:
            candidates.append(summary)
        if narration:
            candidates.extend(re.split(r"[。！？\n]", narration))
        candidates.extend(self._collect_dialogue_lines(scene))

        important = []
        for item in candidates:
            text = str(item or "").strip()
            if not text:
                continue
            if any(keyword in text for keyword in self.IMPORTANT_KEYWORDS):
                important.append(text)
            if len(important) >= 3:
                break
        if not important and summary:
            important.append(summary)
        return " / ".join(important) if important else None

    def upsert_memory(self, payload: dict):
        return self._repo.upsert(payload)

    def list_recent(self, project_id: int, chapter_id: int | None = None, limit: int = 8):
        return self._repo.list_recent(project_id, chapter_id=chapter_id, limit=limit)

    def sync_scene_memories(self, scene):
        if scene is None:
            return []

        records = []
        digest = self._build_scene_digest(scene)
        if digest:
            records.append(
                self._repo.upsert(
                    {
                        "project_id": scene.project_id,
                        "chapter_id": scene.chapter_id,
                        "scene_id": scene.id,
                        "memory_type": "scene_digest",
                        "memory_key": f"scene:{scene.id}:digest",
                        "content_text": digest,
                        "importance": 40,
                    }
                )
            )

        important_note = self._build_important_note(scene)
        if important_note:
            records.append(
                self._repo.upsert(
                    {
                        "project_id": scene.project_id,
                        "chapter_id": scene.chapter_id,
                        "scene_id": scene.id,
                        "memory_type": "conversation_note",
                        "memory_key": f"scene:{scene.id}:important",
                        "content_text": important_note,
                        "importance": 70,
                    }
                )
            )

        player_name = self._extract_player_name(scene)
        if player_name:
            records.append(
                self._repo.upsert(
                    {
                        "project_id": scene.project_id,
                        "chapter_id": None,
                        "scene_id": scene.id,
                        "memory_type": "player_profile",
                        "memory_key": "player_name",
                        "content_text": f"player_name={player_name}",
                        "importance": 100,
                    }
                )
            )
        return records
