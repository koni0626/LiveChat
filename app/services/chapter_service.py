from ..repositories.chapter_repository import ChapterRepository


class ChapterService:
    def __init__(self, repository: ChapterRepository | None = None):
        self._repo = repository or ChapterRepository()

    def list_chapters(self, project_id: int):
        return self._repo.list_by_project(project_id)

    def create_chapter(self, project_id: int, payload: dict):
        return self._repo.create(project_id, payload)

    def get_chapter(self, chapter_id: int):
        return self._repo.get(chapter_id)

    def update_chapter(self, chapter_id: int, payload: dict):
        return self._repo.update(chapter_id, payload)

    def delete_chapter(self, chapter_id: int):
        return self._repo.delete(chapter_id)
