from flask import Blueprint, request

from ...api import NotFoundError, json_response
from ...repositories.character_repository import CharacterRepository
from ...services.closet_service import ClosetService
from ..access import require_project_view


closet_bp = Blueprint("closet", __name__)
closet_service = ClosetService()
character_repository = CharacterRepository()


@closet_bp.route("/projects/<int:project_id>/outfits", methods=["GET"])
def list_project_outfits(project_id: int):
    require_project_view(project_id)
    return json_response(closet_service.list_project_outfits(project_id))


@closet_bp.route("/projects/<int:project_id>/characters/<int:character_id>/outfits", methods=["POST"])
def create_character_outfit(project_id: int, character_id: int):
    _project, user = require_project_view(project_id)
    payload = dict(request.form) if request.form else (request.get_json(silent=True) or {})
    upload_file = request.files.get("file")
    return json_response(closet_service.create_outfit(project_id, character_id, payload, upload_file), status=201)


@closet_bp.route("/projects/<int:project_id>/characters/<int:character_id>/outfits/generate", methods=["POST"])
def generate_character_outfit(project_id: int, character_id: int):
    _project, user = require_project_view(project_id)
    payload = request.get_json(silent=True) or {}
    return json_response(closet_service.generate_outfit_image(project_id, user.id, character_id, payload), status=201)


@closet_bp.route("/characters/<int:character_id>/outfits", methods=["GET"])
def list_character_outfits(character_id: int):
    character = character_repository.get(character_id)
    if not character:
        raise NotFoundError()
    require_project_view(character.project_id)
    outfits = closet_service.list_character_outfits(character_id)
    return json_response(outfits)


@closet_bp.route("/outfits/<int:outfit_id>", methods=["GET"])
def get_outfit(outfit_id: int):
    outfit = closet_service.get_outfit(outfit_id)
    if not outfit:
        raise NotFoundError()
    require_project_view(outfit["project_id"])
    return json_response(outfit)


@closet_bp.route("/outfits/<int:outfit_id>", methods=["PATCH"])
def update_outfit(outfit_id: int):
    outfit = closet_service.get_outfit(outfit_id)
    if not outfit:
        raise NotFoundError()
    require_project_view(outfit["project_id"])
    payload = request.get_json(silent=True) or {}
    updated = closet_service.update_outfit(outfit_id, payload)
    if not updated:
        raise NotFoundError()
    return json_response(updated)


@closet_bp.route("/outfits/<int:outfit_id>", methods=["DELETE"])
def delete_outfit(outfit_id: int):
    outfit = closet_service.get_outfit(outfit_id)
    if not outfit:
        raise NotFoundError()
    require_project_view(outfit["project_id"])
    closet_service.delete_outfit(outfit_id)
    return json_response({"deleted": True})
