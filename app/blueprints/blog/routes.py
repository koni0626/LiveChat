from flask import Blueprint, request

from ...api import ForbiddenError, NotFoundError, ValidationError, json_response
from ...models import User
from ...services.authorization_service import AuthorizationService
from ...services.blog_service import BlogService
from ...services.project_service import ProjectService
from ...services.user_setting_service import UserSettingService
from ..access import current_user_or_401, require_project_manage


blog_bp = Blueprint("blog", __name__)
blog_service = BlogService()
authorization_service = AuthorizationService()
project_service = ProjectService()
user_setting_service = UserSettingService()


def _current_user():
    return current_user_or_401()


def _can_manage_project(user: User, project):
    return authorization_service.can_manage_project(user, project)


def _require_post_manage(post_id: int):
    user = _current_user()
    post = blog_service.get_post(post_id)
    if not post:
        raise NotFoundError()
    project = project_service.get_project(post.project_id)
    if not authorization_service.can_manage_project(user, project) and post.created_by_user_id != user.id:
        raise ForbiddenError()
    return post, user


def _require_post_visible(post_id: int):
    user = _current_user()
    post = blog_service.get_post(post_id)
    if not post:
        raise NotFoundError()
    project = project_service.get_project(post.project_id)
    can_manage = authorization_service.can_manage_project(user, project)
    can_edit = can_manage or post.created_by_user_id == user.id
    if post.status != "published" and not can_edit:
        raise NotFoundError()
    return post, user, can_edit


@blog_bp.route("/blog/posts", methods=["GET"])
def list_posts():
    user = _current_user()
    project_id = request.args.get("project_id", type=int)
    character_id = request.args.get("character_id", type=int)
    status = request.args.get("status")
    search = request.args.get("q") or request.args.get("search")
    include_pagination = str(request.args.get("include_pagination") or "").lower() in {"1", "true", "yes", "on"}
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    per_page = max(1, min(request.args.get("per_page", default=request.args.get("limit", default=20, type=int), type=int) or 20, 50))
    offset = (page - 1) * per_page if include_pagination else 0
    posts = blog_service.list_posts(
        user=user,
        can_manage_project_func=_can_manage_project,
        project_id=project_id,
        character_id=character_id,
        search=search,
        status=status,
        limit=per_page,
        offset=offset,
    )
    if not include_pagination:
        return json_response(posts, meta={"count": len(posts)})
    total = blog_service.count_posts(project_id=project_id, character_id=character_id, search=search, status=status)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return json_response(
        {
            "items": posts,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_prev": page > 1,
                "has_next": page < total_pages,
            },
        },
        meta={"count": len(posts), "total": total},
    )


@blog_bp.route("/blog/posts/<int:post_id>", methods=["GET"])
def get_post(post_id: int):
    post, _, can_manage = _require_post_visible(post_id)
    return json_response(blog_service.serialize_post(post, can_manage=can_manage))


@blog_bp.route("/projects/<int:project_id>/blog/posts", methods=["POST"])
def create_post(project_id: int):
    _, user = require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    try:
        post = blog_service.create_post(project_id=project_id, user_id=user.id, payload=payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(blog_service.serialize_post(post, can_manage=True), status=201)


@blog_bp.route("/projects/<int:project_id>/blog/generate", methods=["POST"])
def generate_blog_post(project_id: int):
    _, user = require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_text_generation_settings(payload)
    try:
        post = blog_service.generate_post(project_id=project_id, user_id=user.id, payload=payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    return json_response(blog_service.serialize_post(post, can_manage=True), status=201)


@blog_bp.route("/blog/posts/<int:post_id>", methods=["PATCH"])
def update_post(post_id: int):
    post, _ = _require_post_manage(post_id)
    payload = request.get_json(silent=True) or {}
    try:
        updated = blog_service.update_post(post.id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not updated:
        raise NotFoundError()
    return json_response(blog_service.serialize_post(updated, can_manage=True))


@blog_bp.route("/blog/posts/<int:post_id>", methods=["DELETE"])
def delete_post(post_id: int):
    post, _ = _require_post_manage(post_id)
    if not blog_service.delete_post(post.id):
        raise NotFoundError()
    return json_response({"post_id": post.id, "deleted": True})


@blog_bp.route("/blog/posts/<int:post_id>/thumbnail/generate", methods=["POST"])
def generate_thumbnail(post_id: int):
    post, _ = _require_post_manage(post_id)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        updated = blog_service.generate_thumbnail(post.id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    return json_response(blog_service.serialize_post(updated, can_manage=True))


@blog_bp.route("/blog/x-schedules", methods=["GET"])
def list_x_schedules():
    _current_user()
    project_id = request.args.get("project_id", type=int)
    start = request.args.get("start")
    end = request.args.get("end")
    return json_response(blog_service.list_x_schedules(project_id=project_id, start=start, end=end))


@blog_bp.route("/blog/posts/<int:post_id>/x-schedule", methods=["POST"])
def schedule_x_post(post_id: int):
    post, user = _require_post_manage(post_id)
    payload = request.get_json(silent=True) or {}
    try:
        schedule = blog_service.schedule_x_post(post.id, user.id, payload.get("scheduled_for"))
    except ValueError as exc:
        raise ValidationError(str(exc))
    return json_response(blog_service.serialize_post(post, can_manage=True) | {"x_schedule": blog_service._serialize_x_schedule(schedule)}, status=201)


@blog_bp.route("/blog/posts/<int:post_id>/x-schedule", methods=["DELETE"])
def cancel_x_post_schedule(post_id: int):
    post, _ = _require_post_manage(post_id)
    schedule_id = request.args.get("schedule_id", type=int)
    schedule = blog_service.cancel_x_schedule(post.id, schedule_id)
    if not schedule:
        raise NotFoundError()
    return json_response({"post_id": post.id, "cancelled": True, "x_schedule": blog_service._serialize_x_schedule(schedule)})


@blog_bp.route("/blog/posts/<int:post_id>/x-publish", methods=["POST"])
def publish_x_post_now(post_id: int):
    post, user = _require_post_manage(post_id)
    try:
        schedule = blog_service.publish_x_post_now(post.id, user.id)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    except Exception as exc:
        return json_response({"message": str(exc)}, status=502)
    if not schedule:
        raise NotFoundError()
    return json_response({"post_id": post.id, "published": True, "x_schedule": blog_service._serialize_x_schedule(schedule)})
