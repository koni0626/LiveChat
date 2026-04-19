from flask import Blueprint, request

from ...api import json_response
from ...services.export_service import ExportService


exports_bp = Blueprint("exports", __name__)
export_service = ExportService()
def _serialize_export_job(export_job):
    if export_job is None:
        return None
    return {
        "id": export_job.id,
        "project_id": export_job.project_id,
        "export_type": export_job.export_type,
        "asset_id": export_job.asset_id,
        "status": export_job.status,
        "options_json": export_job.options_json,
        "started_at": export_job.started_at.isoformat() if getattr(export_job, "started_at", None) else None,
        "finished_at": export_job.finished_at.isoformat() if getattr(export_job, "finished_at", None) else None,
        "error_message": export_job.error_message,
        "created_at": export_job.created_at.isoformat() if getattr(export_job, "created_at", None) else None,
    }


@exports_bp.route("/projects/<int:project_id>/exports", methods=["GET"])
def list_exports(project_id: int):
    limit = request.args.get("limit", type=int)
    export_jobs = export_service.list_exports(project_id, limit=limit)
    data = [_serialize_export_job(export_job) for export_job in export_jobs]
    meta = {"project_id": project_id, "count": len(data)}
    return json_response(data, meta=meta)


@exports_bp.route("/projects/<int:project_id>/exports", methods=["POST"])
def create_export(project_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        export_job = export_service.create_export(project_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_export_job(export_job), status=202)


@exports_bp.route("/exports/<int:export_job_id>", methods=["GET"])
def get_export(export_job_id: int):
    export_job = export_service.get_export(export_job_id)
    if not export_job:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_export_job(export_job))
