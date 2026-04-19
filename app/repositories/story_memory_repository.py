from sqlalchemy import or_

from ..extensions import db
from ..models.story_memory import StoryMemory


class StoryMemoryRepository:
    def get_by_key(self, project_id: int, memory_type: str, memory_key: str):
        return (
            StoryMemory.query.filter(
                StoryMemory.project_id == project_id,
                StoryMemory.memory_type == memory_type,
                StoryMemory.memory_key == memory_key,
            )
            .first()
        )

    def upsert(self, payload: dict):
        memory = self.get_by_key(payload["project_id"], payload["memory_type"], payload["memory_key"])
        if memory is None:
            memory = StoryMemory(
                project_id=payload["project_id"],
                memory_type=payload["memory_type"],
                memory_key=payload["memory_key"],
            )
            db.session.add(memory)

        for field in ("chapter_id", "scene_id", "content_text", "detail_json", "importance"):
            if field in payload:
                setattr(memory, field, payload[field])
        db.session.commit()
        return memory

    def list_recent(self, project_id: int, chapter_id: int | None = None, limit: int = 8):
        query = StoryMemory.query.filter(StoryMemory.project_id == project_id)
        if chapter_id is not None:
            query = query.filter(or_(StoryMemory.chapter_id == chapter_id, StoryMemory.chapter_id.is_(None)))
        return (
            query.order_by(StoryMemory.importance.desc(), StoryMemory.updated_at.desc(), StoryMemory.id.desc())
            .limit(limit)
            .all()
        )
