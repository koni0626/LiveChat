from ..extensions import db
from ..models.generated_candidate import GeneratedCandidate

class GeneratedCandidateRepository:
    def _base_query(self):
        return GeneratedCandidate.query

    def list_by_target(
        self,
        *,
        target_type: str,
        target_id: int,
        candidate_type: str | None = None,
        only_selected: bool | None = None,
        project_id: int | None = None,
    ) -> list[GeneratedCandidate]:
        query = self._base_query().filter(
            GeneratedCandidate.target_type == target_type,
            GeneratedCandidate.target_id == target_id,
        )
        if project_id is not None:
            query = query.filter(GeneratedCandidate.project_id == project_id)
        if candidate_type is not None:
            query = query.filter(GeneratedCandidate.candidate_type == candidate_type)
        if only_selected is True:
            query = query.filter(GeneratedCandidate.is_selected == 1)
        elif only_selected is False:
            query = query.filter(GeneratedCandidate.is_selected == 0)
        return query.order_by(GeneratedCandidate.created_at.desc()).all()

    def list_by_scene(
        self,
        scene_id: int,
        candidate_type: str | None = None,
        only_selected: bool | None = None,
    ) -> list[GeneratedCandidate]:
        return self.list_by_target(
            target_type="scene",
            target_id=scene_id,
            candidate_type=candidate_type,
            only_selected=only_selected,
        )

    def get(self, candidate_id: int) -> GeneratedCandidate | None:
        return self._base_query().filter(GeneratedCandidate.id == candidate_id).first()

    def create_for_target(
        self,
        *,
        project_id: int,
        target_type: str,
        target_id: int,
        candidate_type: str,
        content_text: str | None = None,
        content_json: str | None = None,
        score: float | None = None,
        tags_json: str | None = None,
        is_selected: bool = False,
    ) -> GeneratedCandidate:
        candidate = GeneratedCandidate(
            project_id=project_id,
            target_type=target_type,
            target_id=target_id,
            candidate_type=candidate_type,
            content_text=content_text,
            content_json=content_json,
            score=score,
            tags_json=tags_json,
            is_selected=1 if is_selected else 0,
        )
        db.session.add(candidate)
        db.session.commit()
        return candidate

    def create(self, scene_id: int, payload: dict) -> GeneratedCandidate:
        return self.create_for_target(
            project_id=payload["project_id"],
            target_type="scene",
            target_id=scene_id,
            candidate_type=payload.get("candidate_type", "scene_text"),
            content_text=payload.get("content_text"),
            content_json=payload.get("content_json"),
            score=payload.get("score"),
            tags_json=payload.get("tags_json"),
            is_selected=bool(payload.get("is_selected")),
        )

    def update(self, candidate_id: int, payload: dict) -> GeneratedCandidate | None:
        candidate = self.get(candidate_id)
        if not candidate:
            return None

        updatable_fields = {
            "candidate_type",
            "content_text",
            "content_json",
            "score",
            "tags_json",
        }
        for field in updatable_fields:
            if field in payload:
                setattr(candidate, field, payload[field])
        if "is_selected" in payload:
            candidate.is_selected = 1 if payload["is_selected"] else 0

        db.session.commit()
        return candidate

    def mark_selected(self, candidate_id: int, selected: bool, *, exclusive: bool = False):
        candidate = self.get(candidate_id)
        if not candidate:
            return None
        candidate.is_selected = 1 if selected else 0
        if selected and exclusive:
            (
                GeneratedCandidate.query.filter(
                    GeneratedCandidate.target_type == candidate.target_type,
                    GeneratedCandidate.target_id == candidate.target_id,
                    GeneratedCandidate.candidate_type == candidate.candidate_type,
                    GeneratedCandidate.id != candidate.id,
                ).update({GeneratedCandidate.is_selected: 0}, synchronize_session=False)
            )
        db.session.commit()
        return candidate

    def delete(self, candidate_id: int) -> bool:
        candidate = self.get(candidate_id)
        if not candidate:
            return False
        db.session.delete(candidate)
        db.session.commit()
        return True

    def delete_by_target(
        self,
        *,
        target_type: str,
        target_id: int,
        candidate_type: str | None = None,
    ) -> int:
        query = GeneratedCandidate.query.filter(
            GeneratedCandidate.target_type == target_type,
            GeneratedCandidate.target_id == target_id,
        )
        if candidate_type is not None:
            query = query.filter(GeneratedCandidate.candidate_type == candidate_type)
        deleted = query.delete(synchronize_session=False)
        db.session.commit()
        return deleted

    def delete_by_scene(
        self,
        scene_id: int,
        candidate_type: str | None = None,
    ) -> int:
        return self.delete_by_target(
            target_type="scene",
            target_id=scene_id,
            candidate_type=candidate_type,
        )
