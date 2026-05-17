from flask import Blueprint, request

from ...api import NotFoundError, ValidationError, json_response
from ...services.stamp_service import StampService
from ...services.user_setting_service import UserSettingService
from ..access import require_project_manage, require_project_view


stamps_bp = Blueprint("stamps", __name__)
stamp_service = StampService()
user_setting_service = UserSettingService()


@stamps_bp.route("/projects/<int:project_id>/stamps", methods=["GET"])
def list_stamps(project_id: int):
    require_project_view(project_id)
    character_id = request.args.get("character_id", type=int)
    return json_response(stamp_service.list_stamps(project_id, character_id=character_id))


@stamps_bp.route("/projects/<int:project_id>/stamps/generate", methods=["POST"])
def generate_stamp(project_id: int):
    require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    payload["size"] = payload.get("size") or "1024x1024"
    try:
        stamp = stamp_service.generate_stamp(project_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    return json_response(stamp, status=201)


@stamps_bp.route("/projects/<int:project_id>/stamps/<int:asset_id>", methods=["GET"])
def get_stamp(project_id: int, asset_id: int):
    require_project_view(project_id)
    stamp = stamp_service.get_stamp(project_id, asset_id)
    if not stamp:
        raise NotFoundError()
    return json_response(stamp)


@stamps_bp.route("/projects/<int:project_id>/stamps/<int:asset_id>", methods=["DELETE"])
def delete_stamp(project_id: int, asset_id: int):
    require_project_manage(project_id)
    if not stamp_service.delete_stamp(project_id, asset_id):
        raise NotFoundError()
    return json_response({"asset_id": asset_id, "deleted": True})
