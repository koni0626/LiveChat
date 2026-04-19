from flask import Blueprint, request, session

from ...api import json_response
from ...services.user_setting_service import UserSettingService


settings_bp = Blueprint("settings", __name__)
user_setting_service = UserSettingService()


def _current_user_id() -> int | None:
    return session.get("user_id")


@settings_bp.route("/settings", methods=["GET"])
def get_settings():
    payload = user_setting_service.get_settings(_current_user_id())
    return json_response(payload)


@settings_bp.route("/settings", methods=["PUT"])
def update_settings():
    payload = user_setting_service.update_settings(_current_user_id(), request.get_json(silent=True) or {})
    return json_response(payload)


@settings_bp.route("/settings/reset", methods=["POST"])
def reset_settings():
    payload = user_setting_service.reset_settings(_current_user_id())
    return json_response(payload)
