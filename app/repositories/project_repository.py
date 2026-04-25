from datetime import datetime
from typing import Sequence

from sqlalchemy import or_

from ..extensions import db
from ..models.project import Project


class ProjectRepository:
    MUTABLE_FIELDS: tuple[str, ...] = (
        "title",
        "genre",
        "thumbnail_asset_id",
        "world_id",
        "slug",
        "summary",
        "play_time_minutes",
        "project_type",
        "status",
        "visibility",
        "chat_enabled",
        "settings_json",
    )

    def _base_query(self, include_deleted: bool = False):
        query = Project.query
        if not include_deleted:
            query = query.filter(Project.deleted_at.is_(None))
        return query

    def list_by_owner(
        self,
        owner_user_id: int,
        include_deleted: bool = False,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ):
        query = self._base_query(include_deleted).filter(Project.owner_user_id == owner_user_id)
        if statuses:
            query = query.filter(Project.status.in_(list(statuses)))
        if search:
            keyword = f"%{search.strip()}%"
            query = query.filter(or_(Project.title.ilike(keyword), Project.slug.ilike(keyword)))
        return query.order_by(Project.updated_at.desc(), Project.id.desc()).all()

    def list_all(
        self,
        include_deleted: bool = False,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ):
        query = self._base_query(include_deleted)
        if statuses:
            query = query.filter(Project.status.in_(list(statuses)))
        if search:
            keyword = f"%{search.strip()}%"
            query = query.filter(or_(Project.title.ilike(keyword), Project.slug.ilike(keyword)))
        return query.order_by(Project.updated_at.desc(), Project.id.desc()).all()

    def list_chat_available(
        self,
        include_deleted: bool = False,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ):
        query = self._base_query(include_deleted).filter(
            Project.chat_enabled == 1,
            Project.status == "published",
        )
        if statuses:
            query = query.filter(Project.status.in_(list(statuses)))
        if search:
            keyword = f"%{search.strip()}%"
            query = query.filter(or_(Project.title.ilike(keyword), Project.slug.ilike(keyword)))
        return query.order_by(Project.updated_at.desc(), Project.id.desc()).all()

    def get(self, project_id: int, include_deleted: bool = False):
        return (
            self._base_query(include_deleted)
            .filter(Project.id == project_id)
            .first()
        )

    def get_by_slug(self, owner_user_id: int, slug: str, include_deleted: bool = False):
        return (
            self._base_query(include_deleted)
            .filter(Project.owner_user_id == owner_user_id, Project.slug == slug)
            .first()
        )

    def slug_exists(
        self,
        owner_user_id: int,
        slug: str,
        *,
        exclude_project_id: int | None = None,
    ) -> bool:
        query = self._base_query(include_deleted=True).filter(
            Project.owner_user_id == owner_user_id,
            Project.slug == slug,
        )
        if exclude_project_id:
            query = query.filter(Project.id != exclude_project_id)
        return db.session.query(query.exists()).scalar() is True

    def create(self, owner_user_id: int, payload: dict):
        project = Project(
            owner_user_id=owner_user_id,
            title=payload["title"],
            genre=payload.get("genre") or "未設定",
            thumbnail_asset_id=payload.get("thumbnail_asset_id"),
            world_id=payload.get("world_id"),
            slug=payload.get("slug"),
            summary=payload.get("summary"),
            play_time_minutes=payload.get("play_time_minutes"),
            project_type=payload.get("project_type", "linear"),
            status=payload.get("status", "draft"),
            visibility=payload.get("visibility", "published" if payload.get("status") == "published" else "private"),
            chat_enabled=1 if payload.get("chat_enabled", True) else 0,
            settings_json=payload.get("settings_json"),
        )
        db.session.add(project)
        db.session.commit()
        return project

    def update(self, project_id: int, payload: dict):
        project = self.get(project_id, include_deleted=True)
        if not project or project.deleted_at is not None:
            return None
        for field in (
            "title",
            "genre",
            "thumbnail_asset_id",
            "world_id",
            "slug",
            "summary",
            "play_time_minutes",
            "project_type",
            "status",
            "visibility",
            "chat_enabled",
            "settings_json",
        ):
            if field in payload:
                setattr(project, field, payload[field])
        db.session.commit()
        return project

    def delete(self, project_id: int):
        project = self.get(project_id, include_deleted=True)
        if not project:
            return False
        if project.deleted_at is not None:
            return True
        project.deleted_at = datetime.utcnow()
        db.session.commit()
        return True

    def restore(self, project_id: int):
        project = self.get(project_id, include_deleted=True)
        if not project or project.deleted_at is None:
            return None
        project.deleted_at = None
        db.session.commit()
        return project
