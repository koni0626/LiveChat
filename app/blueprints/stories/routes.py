from flask import Blueprint, request, session

from ...api import ForbiddenError, NotFoundError, UnauthorizedError, ValidationError, json_response
from ...models import User
from ...services.authorization_service import AuthorizationService
from ...services.asset_service import AssetService
from ...services.project_service import ProjectService
from ...services.story_service import StoryService
from ...services.story_session_service import StorySessionService
from ...services.user_setting_service import UserSettingService


stories_bp = Blueprint("stories", __name__)
authorization_service = AuthorizationService()
asset_service = AssetService()
project_service = ProjectService()
story_service = StoryService()
story_session_service = StorySessionService(story_service=story_service)
user_setting_service = UserSettingService()


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        raise UnauthorizedError()
    user = User.query.get(user_id)
    if not user or not user.is_active_user:
        raise UnauthorizedError()
    return user


def _require_project(project_id: int, *, for_manage: bool = False, for_session_create: bool = False):
    user = _current_user()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if for_manage and not authorization_service.can_manage_project(user, project):
        raise ForbiddenError()
    if for_session_create and not authorization_service.can_create_chat_session(user, project):
        raise ForbiddenError()
    if not for_manage and not for_session_create and not authorization_service.can_view_project(user, project):
        raise NotFoundError()
    return project, user


def _require_story(story_id: int, *, for_manage: bool = False, published_only: bool = False):
    user = _current_user()
    story = story_service.get_story(story_id)
    if not story:
        raise NotFoundError()
    project = project_service.get_project(story.project_id)
    if not project:
        raise NotFoundError()
    if for_manage:
        if not authorization_service.can_manage_project(user, project):
            raise ForbiddenError()
    else:
        if not authorization_service.can_view_project(user, project):
            raise NotFoundError()
        if published_only and story.status != "published" and not authorization_service.can_manage_project(user, project):
            raise NotFoundError()
    return story, project, user


def _require_story_session(session_id: int):
    user = _current_user()
    story_session = story_session_service.get_session(session_id)
    if not story_session:
        raise NotFoundError()
    project = project_service.get_project(story_session.project_id)
    if not project:
        raise NotFoundError()
    can_view = authorization_service.can_manage_project(user, project) or story_session.owner_user_id == user.id
    if not can_view:
        raise NotFoundError()
    return story_session, project, user


@stories_bp.route("/projects/<int:project_id>/stories", methods=["GET"])
def list_project_stories(project_id: int):
    project, user = _require_project(project_id)
    include_unpublished = authorization_service.can_manage_project(user, project)
    stories = story_service.list_stories(project_id, include_unpublished=include_unpublished)
    return json_response(story_service.serialize_stories(stories, include_counts=True, owner_user_id=user.id))


@stories_bp.route("/projects/<int:project_id>/stories", methods=["POST"])
def create_project_story(project_id: int):
    _, user = _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        story = story_service.create_story(project_id, payload, created_by_user_id=user.id)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not story:
        raise NotFoundError()
    return json_response(story_service.serialize_story(story, include_counts=True, owner_user_id=user.id), status=201)


@stories_bp.route("/projects/<int:project_id>/stories/draft-markdown", methods=["POST"])
def draft_project_story_markdown(project_id: int):
    _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        result = story_service.generate_markdown_draft(project_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/stories/<int:story_id>", methods=["GET"])
def get_story(story_id: int):
    story, _, user = _require_story(story_id)
    return json_response(story_service.serialize_story(story, include_counts=True, owner_user_id=user.id))


@stories_bp.route("/stories/<int:story_id>/sessions", methods=["GET"])
def list_story_sessions(story_id: int):
    story, project, user = _require_story(story_id, published_only=True)
    owner_user_id = None if authorization_service.can_manage_project(user, project) and request.args.get("scope") == "all" else user.id
    sessions = story_session_service.list_sessions_by_story(story.id, owner_user_id=owner_user_id)
    return json_response(story_session_service.serialize_sessions(sessions))


@stories_bp.route("/stories/<int:story_id>", methods=["PATCH"])
def update_story(story_id: int):
    _require_story(story_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        story = story_service.update_story(story_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not story:
        raise NotFoundError()
    return json_response(story_service.serialize_story(story, include_counts=True))


@stories_bp.route("/stories/<int:story_id>", methods=["DELETE"])
def delete_story(story_id: int):
    _require_story(story_id, for_manage=True)
    if not story_service.delete_story(story_id):
        raise NotFoundError()
    return json_response({"story_id": story_id, "deleted": True})


@stories_bp.route("/stories/<int:story_id>/analyze-config", methods=["POST"])
def analyze_story_config(story_id: int):
    _require_story(story_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        story = story_service.analyze_config(story_id, payload.get("config_markdown"), max_turns=payload.get("max_turns"))
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not story:
        raise NotFoundError()
    return json_response(story_service.serialize_story(story, include_counts=True))


@stories_bp.route("/stories/<int:story_id>/opening-image", methods=["POST"])
def generate_story_opening_image(story_id: int):
    _, _, user = _require_story(story_id, for_manage=True)
    try:
        settings = user_setting_service.apply_image_generation_settings(user.id)
        result = story_service.generate_opening_image(
            story_id,
            quality=settings.get("quality") or "medium",
            size=settings.get("size"),
            model=settings.get("model"),
            provider=settings.get("provider"),
        )
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/stories/<int:story_id>/opening-image/upload", methods=["POST"])
def upload_story_opening_image(story_id: int):
    story, project, _ = _require_story(story_id, for_manage=True)
    upload_file = request.files.get("file")
    if upload_file is None:
        raise ValidationError("file is required")
    try:
        asset = asset_service.create_asset(
            project.id,
            {
                "asset_type": "story_opening_image",
                "upload_file": upload_file,
                "metadata_json": '{"source":"manual_upload","mode":"story_opening_image"}',
            },
        )
        result = story_service.register_opening_image_asset(story.id, asset.id)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/projects/<int:project_id>/story-sessions", methods=["GET"])
def list_project_story_sessions(project_id: int):
    project, user = _require_project(project_id)
    owner_user_id = None if authorization_service.can_manage_project(user, project) else user.id
    return json_response(story_session_service.serialize_sessions(story_session_service.list_sessions(project_id, owner_user_id=owner_user_id)))


@stories_bp.route("/stories/<int:story_id>/sessions", methods=["POST"])
def create_story_session(story_id: int):
    _require_story(story_id, published_only=True)
    user = _current_user()
    payload = request.get_json(silent=True) or {}
    try:
        created = story_session_service.create_session_from_story(story_id, payload, owner_user_id=user.id)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not created:
        raise NotFoundError()
    return json_response(created, status=201)


@stories_bp.route("/story-sessions/<int:session_id>", methods=["GET"])
def get_story_session(session_id: int):
    story_session, _, _ = _require_story_session(session_id)
    return json_response(story_session_service.serialize_session(story_session, include_state=True, include_messages=True))


@stories_bp.route("/story-sessions/<int:session_id>/messages", methods=["POST"])
def post_story_session_message(session_id: int):
    _require_story_session(session_id)
    payload = request.get_json(silent=True) or {}
    try:
        result = story_session_service.post_user_message(session_id, payload.get("message_text"))
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/story-sessions/<int:session_id>/choices/<choice_id>/execute", methods=["POST"])
def execute_story_session_choice(session_id: int, choice_id: str):
    _require_story_session(session_id)
    payload = request.get_json(silent=True) or {}
    try:
        result = story_session_service.execute_choice(
            session_id,
            choice_id,
            generate_image=bool(payload.get("generate_image", True)),
        )
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/story-sessions/<int:session_id>/rolls", methods=["POST"])
def roll_story_session_dice(session_id: int):
    _require_story_session(session_id)
    payload = request.get_json(silent=True) or {}
    try:
        result = story_session_service.roll_dice(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/story-sessions/<int:session_id>/auto-line", methods=["POST"])
def generate_story_session_character_line(session_id: int):
    _require_story_session(session_id)
    payload = request.get_json(silent=True) or {}
    try:
        result = story_session_service.generate_character_message(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/story-sessions/<int:session_id>/player-draft", methods=["POST"])
def generate_story_session_player_draft(session_id: int):
    _require_story_session(session_id)
    payload = request.get_json(silent=True) or {}
    try:
        result = story_session_service.generate_player_draft(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/story-sessions/<int:session_id>/images", methods=["POST"])
def generate_story_session_image(session_id: int):
    _story_session, _project, user = _require_story_session(session_id)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_image_generation_settings(user.id, payload)
    try:
        result = story_session_service.generate_scene_image(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/story-sessions/<int:session_id>/costumes/generate", methods=["POST"])
def generate_story_session_costume(session_id: int):
    _story_session, _project, user = _require_story_session(session_id)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_image_generation_settings(user.id, payload)
    try:
        result = story_session_service.generate_costume(session_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/story-sessions/<int:session_id>/costumes/upload", methods=["POST"])
def upload_story_session_costume(session_id: int):
    story_session, project, _ = _require_story_session(session_id)
    upload_file = request.files.get("file")
    if upload_file is None:
        raise ValidationError("file is required")
    try:
        asset = asset_service.create_asset(
            project.id,
            {
                "asset_type": "uploaded_story_costume_reference",
                "upload_file": upload_file,
                "metadata_json": '{"source":"manual_upload","mode":"story_costume_room"}',
            },
        )
        result = story_session_service.register_uploaded_costume(
            story_session.id,
            asset.id,
            {
                "prompt_text": request.form.get("prompt_text") or None,
                "note": request.form.get("note") or None,
            },
        )
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@stories_bp.route("/story-sessions/<int:session_id>/costumes/<int:image_id>/select", methods=["POST"])
def select_story_session_costume(session_id: int, image_id: int):
    _require_story_session(session_id)
    result = story_session_service.select_costume(session_id, image_id)
    if not result:
        raise NotFoundError()
    return json_response(result)


@stories_bp.route("/story-sessions/<int:session_id>/costumes/<int:image_id>", methods=["DELETE"])
def delete_story_session_costume(session_id: int, image_id: int):
    _require_story_session(session_id)
    result = story_session_service.delete_costume(session_id, image_id)
    if not result:
        raise NotFoundError()
    return json_response(result)
