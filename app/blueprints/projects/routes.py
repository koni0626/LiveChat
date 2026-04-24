from flask import Blueprint, request, session

from ...api import json_response
from ...services.project_service import ProjectService


projects_bp = Blueprint("projects", __name__)
project_service = ProjectService()
def _serialize_project(project):
    if project is None:
        return None
    return {
        "id": project.id,
        "owner_user_id": project.owner_user_id,
        "thumbnail_asset_id": project.thumbnail_asset_id,
        "world_id": project.world_id,
        "title": project.title,
        "slug": project.slug,
        "genre": project.genre,
        "summary": project.summary,
        "play_time_minutes": project.play_time_minutes,
        "project_type": project.project_type,
        "status": project.status,
        "settings_json": project.settings_json,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "deleted_at": project.deleted_at.isoformat() if project.deleted_at else None,
    }


def _get_owner_user_id():
    return session.get("user_id")


@projects_bp.route("", methods=["GET"])
def list_projects():
    owner_user_id = _get_owner_user_id()
    if not owner_user_id:
        return json_response({"message": "unauthorized"}, status=401)

    include_deleted = request.args.get("include_deleted") in ("1", "true", "True")
    statuses = request.args.getlist("status") or None
    search = request.args.get("search")
    projects = project_service.list_projects(
        owner_user_id,
        include_deleted=include_deleted,
        statuses=statuses,
        search=search,
    )
    data = [_serialize_project(project) for project in projects]
    meta = {"page": 1, "per_page": len(data), "total": len(data)}
    return json_response(data, meta=meta)


@projects_bp.route("", methods=["POST"])
def create_project():
    owner_user_id = _get_owner_user_id()
    if not owner_user_id:
        return json_response({"message": "unauthorized"}, status=401)

    payload = request.get_json(silent=True) or {}
    try:
        project = project_service.create_project(owner_user_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_project(project), status=201)


@projects_bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id: int):
    project = project_service.get_project(project_id)
    if not project:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_project(project))


@projects_bp.route("/<int:project_id>", methods=["PATCH"])
def update_project(project_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        project = project_service.update_project(project_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not project:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_project(project))


@projects_bp.route("/<int:project_id>", methods=["DELETE"])
def delete_project(project_id: int):
    deleted = project_service.delete_project(project_id)
    if not deleted:
        return json_response({"message": "not_found"}, status=404)
    return json_response({"project_id": project_id, "deleted": True})
