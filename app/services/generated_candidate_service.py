from ..repositories.generated_candidate_repository import GeneratedCandidateRepository


class GeneratedCandidateService:
    def __init__(self, repository: GeneratedCandidateRepository | None = None):
        self._repo = repository or GeneratedCandidateRepository()

    def _ensure_payload(self, payload: dict | None) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        return payload

    def _require_fields(self, payload: dict, fields: tuple[str, ...]):
        missing = [field for field in fields if payload.get(field) in (None, "")]
        if missing:
            raise ValueError(f"{', '.join(missing)} is required")

    def list_candidates(
        self,
        scene_id: int,
        *,
        candidate_type: str | None = None,
        only_selected: bool | None = None,
    ):
        return self._repo.list_by_scene(
            scene_id,
            candidate_type=candidate_type,
            only_selected=only_selected,
        )

    def list_candidates_for_target(
        self,
        *,
        target_type: str,
        target_id: int,
        candidate_type: str | None = None,
        only_selected: bool | None = None,
        project_id: int | None = None,
    ):
        return self._repo.list_by_target(
            target_type=target_type,
            target_id=target_id,
            candidate_type=candidate_type,
            only_selected=only_selected,
            project_id=project_id,
        )

    def create_candidate(self, scene_id: int, payload: dict):
        payload = self._ensure_payload(payload)
        self._require_fields(payload, ("project_id", "candidate_type"))
        return self._repo.create(scene_id, payload)

    def create_candidate_for_target(self, payload: dict):
        payload = self._ensure_payload(payload)
        self._require_fields(
            payload,
            ("project_id", "target_type", "target_id", "candidate_type"),
        )
        return self._repo.create_for_target(
            project_id=payload["project_id"],
            target_type=payload["target_type"],
            target_id=payload["target_id"],
            candidate_type=payload["candidate_type"],
            content_text=payload.get("content_text"),
            content_json=payload.get("content_json"),
            score=payload.get("score"),
            tags_json=payload.get("tags_json"),
            is_selected=bool(payload.get("is_selected")),
        )

    def get_candidate(self, candidate_id: int):
        return self._repo.get(candidate_id)

    def update_candidate(self, candidate_id: int, payload: dict):
        payload = self._ensure_payload(payload)
        return self._repo.update(candidate_id, payload)

    def mark_candidate_selected(
        self,
        candidate_id: int,
        selected: bool,
        *,
        exclusive: bool = False,
    ):
        return self._repo.mark_selected(candidate_id, selected, exclusive=exclusive)

    def delete_candidate(self, candidate_id: int):
        return self._repo.delete(candidate_id)

    def delete_candidates_for_scene(self, scene_id: int, candidate_type: str | None = None):
        return self._repo.delete_by_scene(scene_id, candidate_type=candidate_type)
