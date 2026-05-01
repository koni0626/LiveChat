from flask import Blueprint, request

from ...api import ForbiddenError, NotFoundError, json_response
from ...services.user_setting_service import UserSettingService
from ...services.world_map_service import WorldMapService
from ..access import require_project_manage, require_project_view


world_maps_bp = Blueprint("world_maps", __name__)
world_map_service = WorldMapService()
user_setting_service = UserSettingService()


def _require_location_view(location_id: int):
    location = world_map_service.get_location(location_id)
    if not location:
        raise NotFoundError()
    require_project_view(location.project_id)
    return location


def _require_location_manage(location_id: int):
    location = world_map_service.get_location(location_id)
    if not location:
        raise NotFoundError()
    require_project_manage(location.project_id)
    return location


@world_maps_bp.route("/projects/<int:project_id>/world-map", methods=["GET"])
def get_world_map(project_id: int):
    require_project_view(project_id)
    return json_response(world_map_service.get_overview(project_id))


@world_maps_bp.route("/projects/<int:project_id>/world-map/upload", methods=["POST"])
def upload_world_map(project_id: int):
    _project, user = require_project_manage(project_id)
    upload_file = request.files.get("file")
    if not upload_file:
        raise ValueError("画像ファイルを選択してください。")
    image = world_map_service.upload_map_image(project_id, upload_file, user.id)
    return json_response(world_map_service.serialize_map_image(image), status=201)


@world_maps_bp.route("/projects/<int:project_id>/world-map/generate", methods=["POST"])
def generate_world_map(project_id: int):
    _project, user = require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        image = world_map_service.generate_map_image(project_id, payload, user.id)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    return json_response(world_map_service.serialize_map_image(image), status=201)


@world_maps_bp.route("/projects/<int:project_id>/world-map/images/<int:image_id>/select", methods=["POST"])
def select_world_map(project_id: int, image_id: int):
    require_project_manage(project_id)
    image = world_map_service.select_map_image(project_id, image_id)
    if not image:
        raise NotFoundError()
    return json_response(world_map_service.serialize_map_image(image))


@world_maps_bp.route("/projects/<int:project_id>/world-map/images/<int:image_id>", methods=["DELETE"])
def delete_world_map(project_id: int, image_id: int):
    require_project_manage(project_id)
    if not world_map_service.delete_map_image(project_id, image_id):
        raise NotFoundError()
    return json_response({"image_id": image_id, "deleted": True})


@world_maps_bp.route("/projects/<int:project_id>/locations", methods=["GET"])
def list_locations(project_id: int):
    require_project_view(project_id)
    filters = {
        "region": request.args.get("region"),
        "location_type": request.args.get("location_type"),
        "tag": request.args.get("tag"),
        "search": request.args.get("search") or request.args.get("q"),
    }
    if any(str(value or "").strip() for value in filters.values()):
        return json_response(world_map_service.search_locations(project_id, filters))
    return json_response(world_map_service.list_locations(project_id))


@world_maps_bp.route("/projects/<int:project_id>/locations/candidates", methods=["GET"])
def list_location_candidates(project_id: int):
    require_project_manage(project_id)
    return json_response(world_map_service.extract_location_candidates(project_id))


@world_maps_bp.route("/projects/<int:project_id>/locations", methods=["POST"])
def create_location(project_id: int):
    require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    location = world_map_service.create_location(project_id, payload)
    return json_response(world_map_service.serialize_location(location), status=201)


@world_maps_bp.route("/locations/<int:location_id>", methods=["GET"])
def get_location(location_id: int):
    location = _require_location_view(location_id)
    return json_response(world_map_service.serialize_location(location))


@world_maps_bp.route("/locations/<int:location_id>/related-sources", methods=["GET"])
def get_location_related_sources(location_id: int):
    _require_location_view(location_id)
    return json_response(world_map_service.related_sources(location_id))


@world_maps_bp.route("/locations/<int:location_id>", methods=["PATCH"])
def update_location(location_id: int):
    _require_location_manage(location_id)
    payload = request.get_json(silent=True) or {}
    location = world_map_service.update_location(location_id, payload)
    if not location:
        raise NotFoundError()
    return json_response(world_map_service.serialize_location(location))


@world_maps_bp.route("/locations/<int:location_id>", methods=["DELETE"])
def delete_location(location_id: int):
    _require_location_manage(location_id)
    if not world_map_service.delete_location(location_id):
        raise NotFoundError()
    return json_response({"location_id": location_id, "deleted": True})


@world_maps_bp.route("/locations/<int:location_id>/image/upload", methods=["POST"])
def upload_location_image(location_id: int):
    _require_location_manage(location_id)
    upload_file = request.files.get("file")
    if not upload_file:
        raise ValueError("画像ファイルを選択してください。")
    location = world_map_service.upload_location_image(location_id, upload_file)
    return json_response(world_map_service.serialize_location(location))


@world_maps_bp.route("/locations/<int:location_id>/image/generate", methods=["POST"])
def generate_location_image(location_id: int):
    location = _require_location_manage(location_id)
    payload = request.get_json(silent=True) or {}
    _project, user = require_project_manage(location.project_id)
    payload = user_setting_service.apply_global_image_generation_settings(payload)
    try:
        location = world_map_service.generate_location_image(location_id, payload)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    return json_response(world_map_service.serialize_location(location))
