import json

from flask import Blueprint, request, session

from ...api import NotFoundError, UnauthorizedError, ValidationError, json_response
from ...services.asset_service import AssetService
from ...services.chat_session_service import ChatSessionService
from ...services.live_chat_service import LiveChatService
from ...services.project_service import ProjectService
from ...services.session_state_service import SessionStateService


chat_bp = Blueprint("chat", __name__)
live_chat_service = LiveChatService()
project_service = ProjectService()
asset_service = AssetService()
chat_session_service = ChatSessionService()
session_state_service = SessionStateService()


def _require_user_id():
    user_id = session.get("user_id")
    if not user_id:
        raise UnauthorizedError()
    return int(user_id)


def _require_project(project_id: int):
    user_id = _require_user_id()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if project.owner_user_id != user_id:
        raise UnauthorizedError()
    return project


def _require_session(session_id: int):
    user_id = _require_user_id()
    chat_session = chat_session_service.get_session(session_id)
    if not chat_session:
        raise NotFoundError()
    project = project_service.get_project(chat_session.project_id)
    if not project:
        raise NotFoundError()
    if project.owner_user_id != user_id:
        raise UnauthorizedError()
    return chat_session, project


@chat_bp.route("/chat/sessions", methods=["GET"])
def list_chat_sessions():
    project_id = request.args.get("project_id", type=int)
    if not project_id:
        raise ValidationError("project_id is required")
    _require_project(project_id)
    return json_response(live_chat_service.list_sessions(project_id))


@chat_bp.route("/chat/sessions", methods=["POST"])
def create_chat_session():
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    if not project_id:
        raise ValidationError("project_id is required")
    _require_project(int(project_id))
    created = live_chat_service.create_session(int(project_id), payload)
    if not created:
        raise NotFoundError()
    return json_response(created, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>", methods=["GET"])
def get_chat_session(session_id: int):
    _require_session(session_id)
    context = live_chat_service.get_session_context(session_id)
    if not context:
        raise NotFoundError()
    return json_response(context)


@chat_bp.route("/chat/sessions/<int:session_id>", methods=["PATCH"])
def update_chat_session(session_id: int):
    _require_session(session_id)
    payload = request.get_json(silent=True) or {}
    updated = live_chat_service.update_session(session_id, payload)
    if not updated:
        raise NotFoundError()
    return json_response(updated)


@chat_bp.route("/chat/sessions/<int:session_id>", methods=["DELETE"])
def delete_chat_session(session_id: int):
    _require_session(session_id)
    deleted = chat_session_service.delete_session(session_id)
    if not deleted:
        raise NotFoundError()
    return json_response({"session_id": session_id, "deleted": True})


@chat_bp.route("/chat/sessions/<int:session_id>/messages", methods=["GET"])
def list_chat_messages(session_id: int):
    _require_session(session_id)
    context = live_chat_service.get_session_context(session_id)
    return json_response(context["messages"], meta={"count": len(context["messages"])})


@chat_bp.route("/chat/sessions/<int:session_id>/messages", methods=["POST"])
def post_chat_message(session_id: int):
    _require_session(session_id)
    payload = request.get_json(silent=True) or {}
    result = live_chat_service.post_message(session_id, payload)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/messages/<int:message_id>", methods=["DELETE"])
def delete_chat_message(session_id: int, message_id: int):
    _require_session(session_id)
    result = live_chat_service.delete_message(session_id, message_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/state", methods=["GET"])
def get_chat_state(session_id: int):
    _require_session(session_id)
    state = session_state_service.get_state(session_id)
    return json_response(live_chat_service._serialize_state(state))


@chat_bp.route("/chat/sessions/<int:session_id>/state/extract", methods=["POST"])
def extract_chat_state(session_id: int):
    _require_session(session_id)
    state = live_chat_service.extract_state(session_id)
    if not state:
        raise NotFoundError()
    return json_response(state)


@chat_bp.route("/chat/sessions/<int:session_id>/images", methods=["GET"])
def list_chat_images(session_id: int):
    _require_session(session_id)
    context = live_chat_service.get_session_context(session_id)
    return json_response(context["images"], meta={"count": len(context["images"])})


@chat_bp.route("/chat/sessions/<int:session_id>/images/generate", methods=["POST"])
def generate_chat_image(session_id: int):
    _require_session(session_id)
    payload = request.get_json(silent=True) or {}
    result = live_chat_service.generate_image(session_id, payload)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/images/upload", methods=["POST"])
def upload_chat_image(session_id: int):
    chat_session, project = _require_session(session_id)
    upload_file = request.files.get("file")
    if upload_file is None:
        raise ValidationError("file is required")
    asset = asset_service.create_asset(
        project.id,
        {
            "asset_type": "uploaded_live_chat_image",
            "upload_file": upload_file,
            "metadata_json": '{"source":"manual_upload","mode":"live_chat"}',
        },
    )
    state_json = request.form.get("state_json")
    if state_json:
        try:
            state_json = json.loads(state_json)
        except ValueError:
            pass
    result = live_chat_service.register_uploaded_image(
        chat_session.id,
        asset.id,
        {
            "image_type": request.form.get("image_type") or "live_scene",
            "prompt_text": request.form.get("prompt_text") or None,
            "quality": request.form.get("quality") or "external",
            "size": request.form.get("size") or "uploaded",
            "state_json": state_json,
            "is_selected": str(request.form.get("is_selected", "1")).lower() in {"1", "true", "yes", "on"},
        },
    )
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/images/<int:image_id>/select", methods=["POST"])
def select_chat_image(session_id: int, image_id: int):
    _require_session(session_id)
    result = live_chat_service.select_image(image_id)
    if not result:
        raise NotFoundError()
    return json_response(result)
