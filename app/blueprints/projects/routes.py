import os

from flask import Blueprint, current_app, request, session

from ...api import ForbiddenError, NotFoundError, UnauthorizedError, json_response
from ...models import User
from ...services.asset_service import AssetService
from ...services.authorization_service import AuthorizationService
from ...services.project_service import ProjectService


projects_bp = Blueprint("projects", __name__)
project_service = ProjectService()
authorization_service = AuthorizationService()
asset_service = AssetService()


def _project_status(status):
    return "published" if status in {"published", "active"} else "draft"


def _build_media_url(file_path: str | None):
    if not file_path:
        return None
    storage_root = current_app.config.get("STORAGE_ROOT")
    normalized_path = os.path.normpath(file_path)
    normalized_root = os.path.normpath(storage_root)
    if not normalized_path.startswith(normalized_root):
        return None
    relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
    return f"/media/{relative}"


def _serialize_asset_summary(asset_id: int | None):
    if not asset_id:
        return None
    asset = asset_service.get_asset(asset_id)
    if not asset:
        return None
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "file_name": asset.file_name,
        "media_url": _build_media_url(asset.file_path),
        "mime_type": asset.mime_type,
        "width": asset.width,
        "height": asset.height,
    }


def _serialize_project(project):
    if project is None:
        return None
    return {
        "id": project.id,
        "owner_user_id": project.owner_user_id,
        "thumbnail_asset_id": project.thumbnail_asset_id,
        "thumbnail_asset": _serialize_asset_summary(project.thumbnail_asset_id),
        "world_id": project.world_id,
        "title": project.title,
        "slug": project.slug,
        "genre": project.genre,
        "summary": project.summary,
        "play_time_minutes": project.play_time_minutes,
        "project_type": project.project_type,
        "status": _project_status(project.status),
        "visibility": getattr(project, "visibility", "private"),
        "chat_enabled": bool(getattr(project, "chat_enabled", 1)),
        "settings_json": project.settings_json,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "deleted_at": project.deleted_at.isoformat() if project.deleted_at else None,
    }


def _get_owner_user_id():
    return session.get("user_id")


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        raise UnauthorizedError()
    user = User.query.get(user_id)
    if not user or not user.is_active_user:
        raise UnauthorizedError()
    return user


@projects_bp.route("", methods=["GET"])
def list_projects():
    user = _current_user()
    include_deleted = request.args.get("include_deleted") in ("1", "true", "True")
    statuses = request.args.getlist("status") or None
    search = request.args.get("search")
    if authorization_service.is_superuser(user):
        projects = project_service.list_all_projects(
            include_deleted=include_deleted,
            statuses=statuses,
            search=search,
        )
    elif authorization_service.is_project_user(user):
        projects = project_service.list_projects(
            user.id,
            include_deleted=include_deleted,
            statuses=statuses,
            search=search,
        )
    else:
        projects = project_service.list_chat_available_projects(
            include_deleted=False,
            statuses=statuses,
            search=search,
        )
    data = [_serialize_project(project) for project in projects]
    meta = {"page": 1, "per_page": len(data), "total": len(data)}
    return json_response(data, meta=meta)


@projects_bp.route("", methods=["POST"])
def create_project():
    user = _current_user()
    if not authorization_service.can_create_project(user):
        raise ForbiddenError()

    payload = request.get_json(silent=True) or {}
    try:
        project = project_service.create_project(user.id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_project(project), status=201)


@projects_bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id: int):
    user = _current_user()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if not authorization_service.can_view_project(user, project):
        raise NotFoundError()
    return json_response(_serialize_project(project))


@projects_bp.route("/<int:project_id>/signboard/generate", methods=["POST"])
def generate_project_signboard(project_id: int):
    user = _current_user()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if not authorization_service.can_manage_project(user, project):
        raise ForbiddenError()
    payload = request.get_json(silent=True) or {}
    try:
        project = project_service.generate_signboard_image(project_id, payload)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    if not project:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_project(project))


@projects_bp.route("/<int:project_id>", methods=["PATCH"])
def update_project(project_id: int):
    user = _current_user()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if not authorization_service.can_manage_project(user, project):
        raise ForbiddenError()
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
    user = _current_user()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if not authorization_service.can_manage_project(user, project):
        raise ForbiddenError()
    deleted = project_service.delete_project(project_id)
    if not deleted:
        return json_response({"message": "not_found"}, status=404)
    return json_response({"project_id": project_id, "deleted": True})
