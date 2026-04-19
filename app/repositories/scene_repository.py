from datetime import datetime

from sqlalchemy import and_, func, or_

from ..extensions import db
from ..models.scene import Scene


class SceneRepository:
    MUTABLE_FIELDS: tuple[str, ...] = (
        'chapter_id',
        'parent_scene_id',
        'scene_key',
        'title',
        'summary',
        'narration_text',
        'dialogue_json',
        'scene_state_json',
        'image_prompt_text',
        'sort_order',
        'active_version_id',
        'is_fixed',
    )

    def _base_query(self, include_deleted: bool = False):
        query = Scene.query
        if not include_deleted:
            query = query.filter(Scene.deleted_at.is_(None))
        return query

    def _next_sort_order(self, chapter_id: int) -> int:
        max_sort = (
            db.session.query(func.coalesce(func.max(Scene.sort_order), 0))
            .filter(Scene.chapter_id == chapter_id)
            .scalar()
        )
        return (max_sort or 0) + 1

    def list_by_project(self, project_id: int, include_deleted: bool = False):
        return (
            self._base_query(include_deleted)
            .filter(Scene.project_id == project_id)
            .order_by(Scene.sort_order.asc(), Scene.id.asc())
            .all()
        )

    def list_by_chapter(self, chapter_id: int, include_deleted: bool = False):
        return (
            self._base_query(include_deleted)
            .filter(Scene.chapter_id == chapter_id)
            .order_by(Scene.sort_order.asc(), Scene.id.asc())
            .all()
        )

    def list_children(self, parent_scene_id: int, include_deleted: bool = False):
        return (
            self._base_query(include_deleted)
            .filter(Scene.parent_scene_id == parent_scene_id)
            .order_by(Scene.sort_order.asc(), Scene.id.asc())
            .all()
        )

    def list_previous_in_chapter(
        self,
        chapter_id: int,
        sort_order: int,
        scene_id: int,
        *,
        limit: int = 3,
        include_deleted: bool = False,
    ):
        items = (
            self._base_query(include_deleted)
            .filter(Scene.chapter_id == chapter_id)
            .filter(
                or_(
                    Scene.sort_order < sort_order,
                    and_(Scene.sort_order == sort_order, Scene.id < scene_id),
                )
            )
            .order_by(Scene.sort_order.desc(), Scene.id.desc())
            .limit(limit)
            .all()
        )
        return list(reversed(items))

    def get(self, scene_id: int, include_deleted: bool = False):
        return (
            self._base_query(include_deleted)
            .filter(Scene.id == scene_id)
            .first()
        )

    def create(self, project_id: int, chapter_id: int, payload: dict):
        sort_order = payload.get("sort_order")
        if sort_order is None:
            sort_order = self._next_sort_order(chapter_id)

        scene = Scene(
            project_id=project_id,
            chapter_id=chapter_id,
            parent_scene_id=payload.get("parent_scene_id"),
            scene_key=payload.get("scene_key"),
            title=payload.get("title"),
            summary=payload.get("summary"),
            narration_text=payload.get("narration_text"),
            dialogue_json=payload.get("dialogue_json"),
            scene_state_json=payload.get("scene_state_json"),
            image_prompt_text=payload.get("image_prompt_text"),
            sort_order=sort_order,
            active_version_id=payload.get("active_version_id"),
            is_fixed=1 if payload.get("is_fixed") else 0,
        )
        db.session.add(scene)
        db.session.commit()
        return scene

    def update(self, scene_id: int, payload: dict):
        scene = self.get(scene_id, include_deleted=True)
        if not scene or scene.deleted_at is not None:
            return None
        updatable_fields = (
            "chapter_id",
            "parent_scene_id",
            "scene_key",
            "title",
            "summary",
            "narration_text",
            "dialogue_json",
            "scene_state_json",
            "image_prompt_text",
            "sort_order",
            "active_version_id",
            "is_fixed",
        )
        for field in updatable_fields:
            if field in payload:
                setattr(scene, field, payload[field])
        db.session.commit()
        return scene

    def delete(self, scene_id: int):
        scene = self.get(scene_id, include_deleted=True)
        if not scene:
            return False
        if scene.deleted_at is not None:
            return True
        scene.deleted_at = datetime.utcnow()
        db.session.commit()
        return True
