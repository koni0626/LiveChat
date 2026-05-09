from flask import Blueprint, request

from ...api import ForbiddenError, NotFoundError, ValidationError, json_response
from ...services.authorization_service import AuthorizationService
from ...services.character_line_thread_service import CharacterLineThreadService
from ...services.project_service import ProjectService
from ..access import current_user_or_401, require_project_view


character_lines_bp = Blueprint("character_lines", __name__)
line_service = CharacterLineThreadService()
authorization_service = AuthorizationService()
project_service = ProjectService()


def _require_room_visible(room_id: int):
    user = current_user_or_401()
    payload = line_service.get_room_payload(room_id=room_id)
    if not payload:
        raise NotFoundError()
    project = project_service.get_project(payload["room"]["project_id"])
    if not authorization_service.can_view_project(user, project):
        raise ForbiddenError()
    return payload, user


@character_lines_bp.route("/projects/<int:project_id>/line/rooms", methods=["GET"])
def list_rooms(project_id: int):
    _project, user = require_project_view(project_id)
    return json_response(line_service.list_rooms(project_id=project_id, user_id=user.id))


@character_lines_bp.route("/projects/<int:project_id>/line/rooms", methods=["POST"])
def create_room(project_id: int):
    _project, user = require_project_view(project_id)
    payload = request.get_json(silent=True) or {}
    try:
        room = line_service.create_room(project_id=project_id, user_id=user.id, payload=payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(room, status=201)


@character_lines_bp.route("/line/rooms/<int:room_id>", methods=["GET"])
def get_room(room_id: int):
    payload, _user = _require_room_visible(room_id)
    return json_response(payload)


@character_lines_bp.route("/line/rooms/<int:room_id>/messages", methods=["POST"])
def create_message(room_id: int):
    _payload, user = _require_room_visible(room_id)
    if request.content_type and "multipart/form-data" in request.content_type:
        payload = dict(request.form)
        upload_file = request.files.get("file")
    else:
        payload = request.get_json(silent=True) or {}
        upload_file = None
    if upload_file is not None and not getattr(upload_file, "filename", ""):
        raise ValidationError("file is required")
    try:
        result = line_service.generate_room_reply(
            room_id=room_id,
            user_id=user.id,
            body=payload.get("body") or payload.get("theme") or "",
            turns=payload.get("turns") or 20,
            exact_turns=bool(payload.get("exact_turns")),
            use_ai=not bool(payload.get("no_ai")),
            upload_file=upload_file,
        )
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(result, status=201)
