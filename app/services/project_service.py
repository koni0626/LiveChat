from collections.abc import Sequence

from ..repositories.project_repository import ProjectRepository

class ProjectService:
    def __init__(self, repository: ProjectRepository | None = None):
        self._repo = repository or ProjectRepository()

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

    def get_project(self, project_id: int, *, include_deleted: bool = False):
        return self._repo.get(project_id, include_deleted=include_deleted)

    def create_project(self, owner_user_id: int, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        if payload.get("title") in (None, ""):
            raise ValueError("title is required")
        if payload.get("genre") in (None, ""):
            raise ValueError("genre is required")
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
