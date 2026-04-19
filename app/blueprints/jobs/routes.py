from flask import Blueprint

from ...api import json_response
from ...services.job_query_service import JobQueryService

jobs_bp = Blueprint("jobs", __name__)
job_query_service = JobQueryService()
def _progress_from_status(status: str) -> int:
    if status == "queued":
        return 0
    if status == "running":
        return 50
    if status in {"success", "failed"}:
        return 100
    return 0


def _serialize_generation_job(job):
    return {
        "id": job.id,
        "kind": "generation",
        "project_id": job.project_id,
        "job_type": job.job_type,
        "target_type": job.target_type,
        "target_id": job.target_id,
        "model_name": job.model_name,
        "status": job.status,
        "progress": _progress_from_status(job.status),
        "request_json": job.request_json,
        "response_json": job.response_json,
        "started_at": job.started_at.isoformat() if getattr(job, "started_at", None) else None,
        "finished_at": job.finished_at.isoformat() if getattr(job, "finished_at", None) else None,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if getattr(job, "created_at", None) else None,
    }


def _serialize_export_job(job):
    return {
        "id": job.id,
        "kind": "export",
        "project_id": job.project_id,
        "job_type": "export",
        "export_type": job.export_type,
        "asset_id": job.asset_id,
        "status": job.status,
        "progress": _progress_from_status(job.status),
        "options_json": job.options_json,
        "started_at": job.started_at.isoformat() if getattr(job, "started_at", None) else None,
        "finished_at": job.finished_at.isoformat() if getattr(job, "finished_at", None) else None,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if getattr(job, "created_at", None) else None,
    }


@jobs_bp.route("/jobs/<int:job_id>", methods=["GET"])
def get_job(job_id: int):
    result = job_query_service.get_job(job_id)
    if not result:
        return json_response({"message": "not_found"}, status=404)

    if result["kind"] == "generation":
        return json_response(_serialize_generation_job(result["job"]))

    return json_response(_serialize_export_job(result["job"]))
