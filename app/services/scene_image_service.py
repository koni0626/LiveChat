from ..repositories.scene_image_repository import SceneImageRepository


class SceneImageService:
    def __init__(self, repository: SceneImageRepository | None = None):
        self._repo = repository or SceneImageRepository()

    def list_scene_images(self, scene_id: int):
        return self._repo.list_by_scene(scene_id)

    def get_scene_image(self, scene_image_id: int):
        return self._repo.get(scene_image_id)

    def generate_scene_images(self, scene_id: int, payload: dict):
        return self._repo.create_for_scene(scene_id, payload)

    def select_scene_image(self, scene_image_id: int):
        return self._repo.select(scene_image_id)

    def regenerate_scene_image(self, scene_image_id: int, payload: dict):
        return self._repo.regenerate(scene_image_id, payload)
