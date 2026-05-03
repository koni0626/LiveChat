import json

from flask import Blueprint, current_app, request, session

from ...api import ForbiddenError, NotFoundError, UnauthorizedError, ValidationError, json_response
from ...models import User
from ...services.asset_service import AssetService
from ...services.authorization_service import AuthorizationService
from ...services.chat_session_service import ChatSessionService
from ...services.live_chat_room_service import LiveChatRoomService
from ...services.live_chat_service import LiveChatService
from ...services.project_service import ProjectService
from ...services.session_state_service import SessionStateService
from ...services.user_setting_service import UserSettingService


chat_bp = Blueprint("chat", __name__)
live_chat_service = LiveChatService()
project_service = ProjectService()
asset_service = AssetService()
chat_session_service = ChatSessionService()
live_chat_room_service = LiveChatRoomService()
session_state_service = SessionStateService()
authorization_service = AuthorizationService()
user_setting_service = UserSettingService()


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        raise UnauthorizedError()
    user = User.query.get(user_id)
    if not user or not user.is_active_user:
        raise UnauthorizedError()
    return user


def _require_project(project_id: int, *, for_chat_create: bool = False, for_manage: bool = False):
    user = _current_user()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if for_manage and not authorization_service.can_manage_project(user, project):
        raise ForbiddenError()
    if for_chat_create and not authorization_service.can_create_chat_session(user, project):
        raise ForbiddenError()
    if not for_manage and not for_chat_create and not authorization_service.can_view_project(user, project):
        raise NotFoundError()
    return project, user


def _require_session(session_id: int, *, include_body: bool = True, for_manage: bool = False):
    user = _current_user()
    chat_session = chat_session_service.get_session(session_id)
    if not chat_session:
        raise NotFoundError()
    project = project_service.get_project(chat_session.project_id)
    if not project:
        raise NotFoundError()
    allowed = (
        authorization_service.can_manage_chat_session(user, chat_session)
        if for_manage
        else authorization_service.can_view_chat_session(user, chat_session, project, include_body=include_body)
    )
    if not allowed:
        raise NotFoundError() if include_body else ForbiddenError()
    return chat_session, project, user


def _require_room(room_id: int, *, for_manage: bool = False, published_only: bool = False):
    user = _current_user()
    room = live_chat_room_service.get_room(room_id)
    if not room:
        raise NotFoundError()
    project = project_service.get_project(room.project_id)
    if not project:
        raise NotFoundError()
    if for_manage:
        if not authorization_service.can_manage_project(user, project):
            raise ForbiddenError()
    else:
        if not authorization_service.can_view_project(user, project):
            raise NotFoundError()
        if published_only and room.status != "published" and not authorization_service.can_manage_project(user, project):
            raise NotFoundError()
    return room, project, user


@chat_bp.route("/projects/<int:project_id>/chat/rooms", methods=["GET"])
def list_project_chat_rooms(project_id: int):
    project, user = _require_project(project_id)
    include_unpublished = authorization_service.can_manage_project(user, project)
    rooms = live_chat_room_service.list_rooms(project_id, include_unpublished=include_unpublished)
    return json_response(
        live_chat_room_service.serialize_rooms(
            rooms,
            include_counts=True,
            owner_user_id=user.id,
        )
    )


@chat_bp.route("/projects/<int:project_id>/chat/rooms", methods=["POST"])
def create_project_chat_room(project_id: int):
    _, user = _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        room = live_chat_room_service.create_room(project_id, payload, created_by_user_id=user.id)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not room:
        raise NotFoundError()
    return json_response(live_chat_room_service.serialize_room(room, include_counts=True), status=201)


@chat_bp.route("/projects/<int:project_id>/chat/rooms/objective-draft", methods=["POST"])
def build_project_chat_room_objective_draft(project_id: int):
    _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        draft = live_chat_room_service.build_objective_draft(project_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    return json_response(draft)


@chat_bp.route("/projects/<int:project_id>/chat/available-rooms", methods=["GET"])
def list_available_chat_rooms(project_id: int):
    project, user = _require_project(project_id)
    include_unpublished = authorization_service.can_manage_project(user, project)
    rooms = live_chat_room_service.list_rooms(project_id, include_unpublished=include_unpublished)
    return json_response(
        live_chat_room_service.serialize_rooms(
            rooms,
            include_counts=True,
            owner_user_id=user.id,
        )
    )


@chat_bp.route("/chat/rooms/<int:room_id>", methods=["GET"])
def get_chat_room(room_id: int):
    room, _, user = _require_room(room_id)
    return json_response(live_chat_room_service.serialize_room(room, include_counts=True, owner_user_id=user.id))


@chat_bp.route("/chat/rooms/<int:room_id>", methods=["PATCH"])
def update_chat_room(room_id: int):
    _require_room(room_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        room = live_chat_room_service.update_room(room_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not room:
        raise NotFoundError()
    return json_response(live_chat_room_service.serialize_room(room, include_counts=True))


@chat_bp.route("/chat/rooms/<int:room_id>", methods=["DELETE"])
def delete_chat_room(room_id: int):
    _require_room(room_id, for_manage=True)
    if not live_chat_room_service.delete_room(room_id):
        raise NotFoundError()
    return json_response({"room_id": room_id, "deleted": True})


@chat_bp.route("/chat/rooms/<int:room_id>/my-sessions", methods=["GET"])
def list_my_room_sessions(room_id: int):
    room, _, user = _require_room(room_id, published_only=True)
    return json_response(live_chat_service.list_sessions(room.project_id, owner_user_id=user.id, room_id=room.id))


@chat_bp.route("/chat/rooms/<int:room_id>/sessions", methods=["POST"])
def create_room_chat_session(room_id: int):
    _require_room(room_id, published_only=True)
    user = _current_user()
    payload = request.get_json(silent=True) or {}
    try:
        created = live_chat_service.create_session_from_room(room_id, payload, owner_user_id=user.id)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not created:
        raise NotFoundError()
    try:
        requested_size = str(payload.get("size") or "").strip()
        valid_sizes = {"1024x1024", "1024x1536", "1536x1024"}
        image_payload = {"quality": "low"}
        if requested_size in valid_sizes:
            image_payload["size"] = requested_size
        initial_image = live_chat_service.generate_image(
            created["session"]["id"],
            user_setting_service.apply_global_image_generation_settings(image_payload),
        )
        created["initial_image"] = initial_image
    except Exception as exc:  # Keep the session usable even when the image API is temporarily unavailable.
        current_app.logger.exception("initial live chat image generation failed")
        created["image_generation_error"] = str(exc)
    return json_response(created, status=201)


@chat_bp.route("/chat/sessions", methods=["GET"])
def list_chat_sessions():
    project_id = request.args.get("project_id", type=int)
    if not project_id:
        raise ValidationError("project_id is required")
    project, user = _require_project(project_id)
    if authorization_service.can_manage_project(user, project):
        include_private_details = authorization_service.is_superuser(user)
        return json_response(
            live_chat_service.list_sessions(
                project_id,
                owner_user_id=None,
                include_private_details=include_private_details,
                detail_owner_user_id=user.id,
            )
        )
    return json_response(live_chat_service.list_sessions(project_id, owner_user_id=user.id))


@chat_bp.route("/chat/sessions", methods=["POST"])
def create_chat_session():
    payload = request.get_json(silent=True) or {}
    project_id = payload.get("project_id")
    if not project_id:
        raise ValidationError("project_id is required")
    _, user = _require_project(int(project_id), for_chat_create=True)
    created = live_chat_service.create_session(int(project_id), payload, owner_user_id=user.id)
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
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    updated = live_chat_service.update_session(session_id, payload)
    if not updated:
        raise NotFoundError()
    return json_response(updated)


@chat_bp.route("/chat/sessions/<int:session_id>", methods=["DELETE"])
def delete_chat_session(session_id: int):
    _require_session(session_id, for_manage=True)
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
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    result = live_chat_service.post_message(session_id, payload)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/proxy-player-message", methods=["POST"])
def generate_proxy_player_message(session_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.generate_player_proxy_message(session_id)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/idle-message", methods=["POST"])
def post_idle_character_message(session_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.post_idle_character_message(session_id)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/player-reaction", methods=["POST"])
def analyze_chat_player_reaction(session_id: int):
    _require_session(session_id, for_manage=True)
    upload_file = request.files.get("file")
    if upload_file is None:
        raise ValidationError("file is required")
    result = live_chat_service.analyze_player_reaction(session_id, upload_file)
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/short-story", methods=["POST"])
def generate_chat_short_story(session_id: int):
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        result = live_chat_service.generate_short_story(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/short-stories/save", methods=["POST"])
def save_chat_short_story(session_id: int):
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        result = live_chat_service.save_short_story(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/messages/<int:message_id>", methods=["DELETE"])
def delete_chat_message(session_id: int, message_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.delete_message(session_id, message_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/choices/<choice_id>/execute", methods=["POST"])
def execute_chat_scene_choice(session_id: int, choice_id: str):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    result = live_chat_service.execute_scene_choice(session_id, choice_id, payload)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/locations/<int:location_id>/move", methods=["POST"])
def move_chat_session_location(session_id: int, location_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        result = live_chat_service.move_to_location(session_id, location_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/location-services/<int:service_id>/select", methods=["POST"])
def select_chat_location_service(session_id: int, service_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        result = live_chat_service.select_location_service(session_id, service_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/lccd/photo-shoot", methods=["POST"])
def generate_chat_lccd_photo_shoot(session_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_image_generation_settings(user.id, payload)
    try:
        result = live_chat_service.generate_lccd_photo_shoot(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/lccd/enter", methods=["POST"])
def enter_chat_lccd_room(session_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        result = live_chat_service.enter_lccd_room(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/state", methods=["GET"])
def get_chat_state(session_id: int):
    _require_session(session_id)
    state = session_state_service.get_state(session_id)
    return json_response(live_chat_service._serialize_state(state))


@chat_bp.route("/chat/sessions/<int:session_id>/images", methods=["GET"])
def list_chat_images(session_id: int):
    _require_session(session_id)
    context = live_chat_service.get_session_context(session_id)
    return json_response(context["images"], meta={"count": len(context["images"])})


@chat_bp.route("/chat/sessions/<int:session_id>/costumes", methods=["GET"])
def list_chat_costumes(session_id: int):
    _require_session(session_id)
    costumes = live_chat_service.list_costumes(session_id)
    return json_response(costumes, meta={"count": len(costumes)})


@chat_bp.route("/chat/sessions/<int:session_id>/closet-outfits", methods=["GET"])
def list_chat_closet_outfits(session_id: int):
    _require_session(session_id)
    result = live_chat_service.list_closet_outfits(session_id)
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/closet-outfits/<int:outfit_id>/select", methods=["POST"])
def select_chat_closet_outfit(session_id: int, outfit_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.select_closet_outfit(session_id, outfit_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/costumes/generate", methods=["POST"])
def generate_chat_costume(session_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_image_generation_settings(user.id, payload)
    result = live_chat_service.generate_costume(session_id, payload)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/costumes/upload", methods=["POST"])
def upload_chat_costume(session_id: int):
    chat_session, project, _ = _require_session(session_id, for_manage=True)
    upload_file = request.files.get("file")
    if upload_file is None:
        raise ValidationError("file is required")
    asset = asset_service.create_asset(
        project.id,
        {
            "asset_type": "uploaded_costume_reference",
            "upload_file": upload_file,
            "metadata_json": '{"source":"manual_upload","mode":"costume_room"}',
        },
    )
    result = live_chat_service.register_uploaded_costume(
        chat_session.id,
        asset.id,
        {
            "prompt_text": request.form.get("prompt_text") or None,
            "note": request.form.get("note") or None,
        },
    )
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/costumes/<int:image_id>/select", methods=["POST"])
def select_chat_costume(session_id: int, image_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.select_costume(session_id, image_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/costumes/<int:image_id>", methods=["DELETE"])
def delete_chat_costume(session_id: int, image_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.delete_costume(session_id, image_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/images/generate", methods=["POST"])
def generate_chat_image(session_id: int):
    _chat_session, _project, user = _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        result = live_chat_service.generate_image(session_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/images/upload", methods=["POST"])
def upload_chat_image(session_id: int):
    chat_session, project, _ = _require_session(session_id, for_manage=True)
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


@chat_bp.route("/chat/sessions/<int:session_id>/gifts/upload", methods=["POST"])
def upload_chat_gift(session_id: int):
    chat_session, project, _ = _require_session(session_id, for_manage=True)
    upload_file = request.files.get("file")
    if upload_file is None:
        raise ValidationError("file is required")
    asset = asset_service.create_asset(
        project.id,
        {
            "asset_type": "uploaded_live_chat_gift",
            "upload_file": upload_file,
            "metadata_json": '{"source":"gift_upload","mode":"live_chat"}',
        },
    )
    result = live_chat_service.upload_gift(
        chat_session.id,
        asset.id,
        {
            "character_id": request.form.get("character_id", type=int),
            "message_text": request.form.get("message_text") or None,
        },
    )
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@chat_bp.route("/chat/sessions/<int:session_id>/images/<int:image_id>/select", methods=["POST"])
def select_chat_image(session_id: int, image_id: int):
    _require_session(session_id, for_manage=True)
    result = live_chat_service.select_image(image_id, session_id=session_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@chat_bp.route("/chat/sessions/<int:session_id>/images/<int:image_id>/reference", methods=["POST"])
def set_chat_image_reference(session_id: int, image_id: int):
    _require_session(session_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    is_reference = str(payload.get("is_reference", "true")).lower() in {"1", "true", "yes", "on"}
    result = live_chat_service.set_reference_image(session_id, image_id, is_reference)
    if not result:
        raise NotFoundError()
    return json_response(result)
