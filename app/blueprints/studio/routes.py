from flask import Blueprint, request, session

from ...api import ForbiddenError, NotFoundError, UnauthorizedError, ValidationError, json_response
from ...models import User
from ...services.authorization_service import AuthorizationService
from ...services.project_service import ProjectService
from ...services.studio_service import StudioService
from ...services.user_setting_service import UserSettingService


studio_bp = Blueprint("studio", __name__)
authorization_service = AuthorizationService()
project_service = ProjectService()
studio_service = StudioService()
user_setting_service = UserSettingService()


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        raise UnauthorizedError()
    user = User.query.get(user_id)
    if not user or not user.is_active_user:
        raise UnauthorizedError()
    return user


def _require_project(project_id: int):
    user = _current_user()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if not authorization_service.can_view_project(user, project):
        raise ForbiddenError()
    return project, user


@studio_bp.route("/projects/<int:project_id>/studio/images", methods=["GET"])
def list_studio_images(project_id: int):
    _, user = _require_project(project_id)
    return json_response(studio_service.list_images(project_id, user.id))


@studio_bp.route("/projects/<int:project_id>/studio/generate", methods=["POST"])
def generate_studio_image(project_id: int):
    _, user = _require_project(project_id)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        result = studio_service.generate_variant(project_id, user.id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    return json_response(result, status=201)
