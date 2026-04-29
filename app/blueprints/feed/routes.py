from flask import Blueprint, request

from ...api import ForbiddenError, NotFoundError, UnauthorizedError, json_response
from ...models import User
from ...services.authorization_service import AuthorizationService
from ...services.feed_service import FeedService
from ...services.project_service import ProjectService
from ...services.user_setting_service import UserSettingService
from ..access import current_user_or_401, require_project_manage


feed_bp = Blueprint("feed", __name__)
feed_service = FeedService()
authorization_service = AuthorizationService()
project_service = ProjectService()
user_setting_service = UserSettingService()


def _current_user():
    return current_user_or_401()


def _can_manage_project(user: User, project):
    return authorization_service.can_manage_project(user, project)


def _require_post_manage(post_id: int):
    user = _current_user()
    post = feed_service.get_post(post_id)
    if not post:
        raise NotFoundError()
    project = project_service.get_project(post.project_id)
    if not authorization_service.can_manage_project(user, project) and post.created_by_user_id != user.id:
        raise ForbiddenError()
    return post, user


def _require_post_visible(post_id: int):
    user = _current_user()
    post = feed_service.get_post(post_id)
    if not post:
        raise NotFoundError()
    project = project_service.get_project(post.project_id)
    can_manage = authorization_service.can_manage_project(user, project)
    can_edit = can_manage or post.created_by_user_id == user.id
    if post.status != "published" and not can_edit:
        raise NotFoundError()
    return post, user, can_edit


@feed_bp.route("/feed/posts", methods=["GET"])
def list_posts():
    user = _current_user()
    project_id = request.args.get("project_id", type=int)
    character_id = request.args.get("character_id", type=int)
    status = request.args.get("status")
    search = request.args.get("q") or request.args.get("search")
    limit = request.args.get("limit", default=50, type=int)
    posts = feed_service.list_posts(
        user=user,
        can_manage_project_func=_can_manage_project,
        project_id=project_id,
        character_id=character_id,
        search=search,
        status=status,
        limit=limit,
    )
    return json_response(posts, meta={"count": len(posts)})


@feed_bp.route("/feed/ranking/characters", methods=["GET"])
def character_post_ranking():
    _current_user()
    project_id = request.args.get("project_id", type=int)
    limit = request.args.get("limit", default=10, type=int)
    ranking = feed_service.character_post_ranking(project_id=project_id, limit=limit)
    return json_response(ranking, meta={"count": len(ranking)})


@feed_bp.route("/feed/posts/<int:post_id>", methods=["GET"])
def get_post(post_id: int):
    post, user, can_manage = _require_post_visible(post_id)
    return json_response(feed_service.serialize_post(post, can_manage=can_manage))


@feed_bp.route("/projects/<int:project_id>/feed/posts", methods=["POST"])
def create_post(project_id: int):
    _, user = require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    try:
        post = feed_service.create_post(project_id=project_id, user_id=user.id, payload=payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(feed_service.serialize_post(post, can_manage=True), status=201)


@feed_bp.route("/projects/<int:project_id>/feed/import-url", methods=["POST"])
def import_feed_url(project_id: int):
    require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    try:
        result = feed_service.import_from_url(project_id, payload.get("url") or "")
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(result)


@feed_bp.route("/feed/posts/<int:post_id>", methods=["PATCH"])
def update_post(post_id: int):
    post, _ = _require_post_manage(post_id)
    payload = request.get_json(silent=True) or {}
    try:
        updated = feed_service.update_post(post.id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not updated:
        raise NotFoundError()
    return json_response(feed_service.serialize_post(updated, can_manage=True))


@feed_bp.route("/feed/posts/<int:post_id>", methods=["DELETE"])
def delete_post(post_id: int):
    post, _ = _require_post_manage(post_id)
    if not feed_service.delete_post(post.id):
        raise NotFoundError()
    return json_response({"post_id": post.id, "deleted": True})


@feed_bp.route("/feed/posts/<int:post_id>/like", methods=["POST"])
def like_post(post_id: int):
    post, user, can_manage = _require_post_visible(post_id)
    updated = feed_service.set_like(post.id, user.id, True)
    return json_response(feed_service.serialize_post(updated, liked_by_me=True, can_manage=can_manage))


@feed_bp.route("/feed/posts/<int:post_id>/like", methods=["DELETE"])
def unlike_post(post_id: int):
    post, user, can_manage = _require_post_visible(post_id)
    updated = feed_service.set_like(post.id, user.id, False)
    return json_response(feed_service.serialize_post(updated, liked_by_me=False, can_manage=can_manage))


@feed_bp.route("/feed/posts/<int:post_id>/image/upload", methods=["POST"])
def upload_post_image(post_id: int):
    post, _ = _require_post_manage(post_id)
    upload_file = request.files.get("file")
    if not upload_file:
        return json_response({"message": "file is required"}, status=400)
    try:
        updated = feed_service.upload_post_image(post.id, upload_file)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(feed_service.serialize_post(updated, can_manage=True))


@feed_bp.route("/feed/posts/<int:post_id>/image/generate", methods=["POST"])
def generate_post_image(post_id: int):
    post, user = _require_post_manage(post_id)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_image_generation_settings(user.id, payload)
    try:
        updated = feed_service.generate_post_image(post.id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    return json_response(feed_service.serialize_post(updated, can_manage=True))


@feed_bp.route("/characters/<int:character_id>/feed-profile", methods=["GET"])
def get_character_feed_profile(character_id: int):
    user = _current_user()
    profile = feed_service.get_character_feed_profile(character_id)
    if profile is None:
        raise NotFoundError()
    return json_response(profile)


@feed_bp.route("/characters/<int:character_id>/feed-profile/refresh", methods=["POST"])
def refresh_character_feed_profile(character_id: int):
    user = _current_user()
    character = feed_service._character_service.get_character(character_id)
    if not character:
        raise NotFoundError()
    project = project_service.get_project(character.project_id)
    if not authorization_service.can_manage_project(user, project):
        raise ForbiddenError()
    profile = feed_service.refresh_character_feed_profile(character_id)
    return json_response(feed_service.get_character_feed_profile(character_id) or {})
