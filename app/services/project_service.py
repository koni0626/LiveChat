from collections.abc import Sequence

from ..repositories.project_repository import ProjectRepository

class ProjectService:
    VALID_STATUSES = {"draft", "published"}
    LEGACY_STATUS_MAP = {"active": "published", "archived": "draft"}

    def __init__(self, repository: ProjectRepository | None = None):
        self._repo = repository or ProjectRepository()

    def _normalize_status(self, status: str | None) -> str:
        value = str(status or "draft").strip() or "draft"
        value = self.LEGACY_STATUS_MAP.get(value, value)
        if value not in self.VALID_STATUSES:
            raise ValueError("status must be draft or published")
        return value

    def _apply_visibility_from_status(self, payload: dict) -> dict:
        status = self._normalize_status(payload.get("status"))
        visibility = "published" if status == "published" else "private"
        return {**payload, "status": status, "visibility": visibility, "chat_enabled": True}

    def list_projects(
        self,
        owner_user_id: int,
        *,
        include_deleted: bool = False,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ):
        return self._repo.list_by_owner(
            owner_user_id,
            include_deleted=include_deleted,
            statuses=statuses,
            search=search,
        )

    def list_all_projects(
        self,
        *,
        include_deleted: bool = False,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ):
        return self._repo.list_all(
            include_deleted=include_deleted,
            statuses=statuses,
            search=search,
        )

    def list_chat_available_projects(
        self,
        *,
        include_deleted: bool = False,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ):
        return self._repo.list_chat_available(
            include_deleted=include_deleted,
            statuses=statuses,
            search=search,
        )

    def get_project(self, project_id: int, *, include_deleted: bool = False):
        return self._repo.get(project_id, include_deleted=include_deleted)

    def create_project(self, owner_user_id: int, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        if payload.get("title") in (None, ""):
            raise ValueError("title is required")
        payload = self._apply_visibility_from_status(payload)
        slug = payload.get("slug")
        if slug and self._repo.slug_exists(owner_user_id, slug):
            raise ValueError("slug_already_exists")
        return self._repo.create(owner_user_id, payload)

    def update_project(self, project_id: int, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        project = self._repo.get(project_id, include_deleted=True)
        if not project or project.deleted_at is not None:
            return None
        if "status" in payload:
            payload = self._apply_visibility_from_status(payload)
        slug = payload.get("slug")
        if slug and self._repo.slug_exists(
            project.owner_user_id, slug, exclude_project_id=project.id
        ):
            raise ValueError("slug_already_exists")
        return self._repo.update(project_id, payload)

    def delete_project(self, project_id: int):
        return self._repo.delete(project_id)

    def restore_project(self, project_id: int):
        return self._repo.restore(project_id)

    def slug_exists(
        self, owner_user_id: int, slug: str, *, exclude_project_id: int | None = None
    ) -> bool:
        return self._repo.slug_exists(
            owner_user_id, slug, exclude_project_id=exclude_project_id
        )
