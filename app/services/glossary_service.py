from ..repositories.glossary_term_repository import GlossaryTermRepository


class GlossaryService:
    def __init__(self, repository: GlossaryTermRepository | None = None):
        self._repo = repository or GlossaryTermRepository()

    def list_terms(self, project_id: int, *, category: str | None = None, search: str | None = None):
        return self._repo.list_by_project(project_id, category=category, search=search)

    def list_terms_for_world(self, world_id: int, *, category: str | None = None):
        return self._repo.list_by_world(world_id, category=category)

    def get_term(self, term_id: int, *, project_id: int | None = None):
        return self._repo.get(term_id, project_id=project_id)

    def create_term(self, project_id: int | None, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        if payload.get("term") in (None, ""):
            raise ValueError("term is required")
        if project_id is None and payload.get("world_id") in (None, ""):
            raise ValueError("world_id is required")
        term = self._repo.create(project_id, payload)
        if not term:
            raise ValueError("world_not_found")
        return term

    def update_term(self, term_id: int, payload: dict, *, project_id: int | None = None):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        return self._repo.update(term_id, payload, project_id=project_id)

    def delete_term(self, term_id: int, *, project_id: int | None = None):
        return self._repo.delete(term_id, project_id=project_id)
