from sqlalchemy import func

from ..extensions import db
from ..models.chapter import Chapter

class ChapterRepository:
    def list_by_project(self, project_id: int):
        return (
            Chapter.query.filter(Chapter.project_id == project_id)
            .order_by(Chapter.sort_order.asc(), Chapter.id.asc())
            .all()
        )

    def get(self, chapter_id: int):
        return Chapter.query.filter(Chapter.id == chapter_id).first()

    def create(self, project_id: int, payload: dict):
        chapter = Chapter(
            project_id=project_id,
            chapter_no=payload["chapter_no"],
            title=payload["title"],
            summary=payload.get("summary"),
            objective=payload.get("objective"),
            sort_order=payload.get("sort_order", self._next_sort_order(project_id)),
        )
        db.session.add(chapter)
        db.session.commit()
        return chapter

    def update(self, chapter_id: int, payload: dict):
        chapter = self.get(chapter_id)
        if not chapter:
            return None
        for field in ("chapter_no", "title", "summary", "objective", "sort_order"):
            if field in payload:
                setattr(chapter, field, payload[field])
        db.session.commit()
        return chapter

    def delete(self, chapter_id: int):
        chapter = self.get(chapter_id)
        if not chapter:
            return False
        db.session.delete(chapter)
        db.session.commit()
        return True

    def _next_sort_order(self, project_id: int) -> int:
        current = (
            db.session.query(func.coalesce(func.max(Chapter.sort_order), 0))
            .filter(Chapter.project_id == project_id)
            .scalar()
        )
        return current + 1
