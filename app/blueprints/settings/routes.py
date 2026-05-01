from flask import Blueprint, request, session

from ...api import ForbiddenError, UnauthorizedError, json_response
from ...models import User
from ...services.user_setting_service import UserSettingService


settings_bp = Blueprint("settings", __name__)
user_setting_service = UserSettingService()


def _current_user_id() -> int | None:
    return session.get("user_id")


def _require_superuser():
    user_id = _current_user_id()
    if not user_id:
        raise UnauthorizedError()
    user = User.query.get(user_id)
    if not user or not user.is_active_user:
        raise UnauthorizedError()
    if user.role != "superuser":
        raise ForbiddenError()
    return user


@settings_bp.route("/settings", methods=["GET"])
def get_settings():
    _require_superuser()
    payload = user_setting_service.get_global_settings()
    return json_response(payload)


@settings_bp.route("/settings", methods=["PUT"])
def update_settings():
    _require_superuser()
    payload = user_setting_service.update_global_settings(request.get_json(silent=True) or {})
    return json_response(payload)


@settings_bp.route("/settings/reset", methods=["POST"])
def reset_settings():
    _require_superuser()
    payload = user_setting_service.reset_global_settings()
    return json_response(payload)
