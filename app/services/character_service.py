from ..repositories.character_repository import CharacterRepository


class CharacterService:
    def __init__(self, repository: CharacterRepository | None = None):
        self._repo = repository or CharacterRepository()

    def list_characters(self, project_id: int, include_deleted: bool = False):
        return self._repo.list_by_project(project_id, include_deleted=include_deleted)

    def create_character(self, project_id: int, payload: dict):
        return self._repo.create(project_id, payload)

    def get_character(self, character_id: int, include_deleted: bool = False):
        return self._repo.get(character_id, include_deleted=include_deleted)

    def update_character(self, character_id: int, payload: dict):
        return self._repo.update(character_id, payload)

    def delete_character(self, character_id: int):
        return self._repo.delete(character_id)

    def restore_character(self, character_id: int):
        return self._repo.restore(character_id)
