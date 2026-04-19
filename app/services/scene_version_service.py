from ..repositories.scene_version_repository import SceneVersionRepository

class SceneVersionService:
    def __init__(self, repository: SceneVersionRepository | None = None):
        self._repo = repository or SceneVersionRepository()
    def list_versions(self, scene_id: int):
        return self._repo.list_by_scene(scene_id)

    def get_version(self, version_id: int):
        return self._repo.get(version_id)

    def create_version(self, scene_id: int, payload: dict):
        return self._repo.create(scene_id, payload)

    def update_version(self, version_id: int, payload: dict):
        return self._repo.update(version_id, payload)

    def adopt_version(self, scene_id: int, version_id: int):
        return self._repo.adopt(scene_id, version_id)

    def delete_version(self, version_id: int):
        return self._repo.delete(version_id)
