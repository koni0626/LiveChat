from ..extensions import db
from ..models.generation_job import GenerationJob


class GenerationJobRepository:
    MUTABLE_FIELDS: tuple[str, ...] = (
        "project_id",
        "job_type",
        "target_type",
        "target_id",
        "model_name",
        "request_json",
        "response_json",
        "status",
        "started_at",
        "finished_at",
        "error_message",
    )

    def create(self, payload: dict):
        job = GenerationJob(**{field: payload.get(field) for field in self.MUTABLE_FIELDS})
        db.session.add(job)
        db.session.commit()
        return job

    def update(self, job: GenerationJob, payload: dict):
        for field in self.MUTABLE_FIELDS:
            if field in payload:
                setattr(job, field, payload[field])
        db.session.commit()
        return job
