from ..repositories.session_image_repository import SessionImageRepository


class SessionImageService:
    def __init__(self, repository: SessionImageRepository | None = None):
        self._repo = repository or SessionImageRepository()

    def list_session_images(self, session_id: int):
        return self._repo.list_by_session(session_id)

    def list_costumes(self, session_id: int):
        return self._repo.list_costumes_by_session(session_id)

    def list_costume_library(self, session_id: int):
        return self._repo.list_costumes_for_session_library(session_id)

    def get_selected_costume(self, session_id: int):
        return self._repo.get_selected_costume(session_id)

    def get_session_image(self, session_image_id: int):
        return self._repo.get(session_image_id)

    def create_session_image(self, session_id: int, payload: dict):
        return self._repo.create_for_session(session_id, payload)

    def create_costume_link_for_session(self, session_id: int, source_image_id: int):
        return self._repo.create_costume_link_for_session(session_id, source_image_id)

    def select_session_image(self, session_image_id: int):
        return self._repo.select(session_image_id)

    def delete_costume(self, session_id: int, session_image_id: int):
        return self._repo.delete_costume(session_id, session_image_id)

    def set_reference(self, session_id: int, session_image_id: int, is_reference: bool):
        return self._repo.set_reference(session_id, session_image_id, is_reference)
