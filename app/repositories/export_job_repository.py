from ..extensions import db
from ..models.export_job import ExportJob

class ExportJobRepository:
    def list_by_project(self, project_id: int, limit: int | None = None):
        query = (
            ExportJob.query.filter(ExportJob.project_id == project_id)
            .order_by(ExportJob.created_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def create(self, project_id: int, payload: dict):
        export_job = ExportJob(
            project_id=project_id,
            export_type=payload["export_type"],
            asset_id=payload.get("asset_id"),
            status=payload.get("status", "queued"),
            options_json=payload.get("options_json"),
            started_at=payload.get("started_at"),
            finished_at=payload.get("finished_at"),
            error_message=payload.get("error_message"),
        )
        db.session.add(export_job)
        db.session.commit()
        return export_job

    def get_by_id(self, export_job_id: int):
        return ExportJob.query.filter(ExportJob.id == export_job_id).first()

    def update(self, export_job_id: int, payload: dict):
        export_job = self.get_by_id(export_job_id)
        if not export_job:
            return None
        for field in (
            "status",
            "options_json",
            "started_at",
            "finished_at",
            "error_message",
            "asset_id",
        ):
            if field in payload:
                setattr(export_job, field, payload[field])
        db.session.commit()
        return export_job
