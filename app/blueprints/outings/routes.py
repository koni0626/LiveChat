from flask import Blueprint, request

from ...api import NotFoundError, json_response
from ...services.outing_service import OutingService
from ..access import current_user_or_401, require_project_view


outings_bp = Blueprint("outings", __name__)
outing_service = OutingService()


@outings_bp.route("/projects/<int:project_id>/outings/options", methods=["GET"])
def outing_options(project_id: int):
    _project, user = require_project_view(project_id)
    return json_response(outing_service.options(project_id, user.id))


@outings_bp.route("/projects/<int:project_id>/outings", methods=["GET"])
def list_outings(project_id: int):
    _project, user = require_project_view(project_id)
    return json_response(outing_service.list_outings(project_id, user.id))


@outings_bp.route("/projects/<int:project_id>/outings", methods=["POST"])
def start_outing(project_id: int):
    _project, user = require_project_view(project_id)
    payload = request.get_json(silent=True) or {}
    return json_response(outing_service.start_outing(project_id, user.id, payload), status=201)


@outings_bp.route("/outings/<int:outing_id>", methods=["GET"])
def get_outing(outing_id: int):
    user = current_user_or_401()
    outing = outing_service.get_outing(outing_id, user.id)
    if not outing:
        raise NotFoundError()
    require_project_view(outing["project_id"])
    return json_response(outing)


@outings_bp.route("/outings/<int:outing_id>/choose", methods=["POST"])
def choose_outing(outing_id: int):
    user = current_user_or_401()
    payload = request.get_json(silent=True) or {}
    outing = outing_service.choose(outing_id, user.id, payload)
    if not outing:
        raise NotFoundError()
    require_project_view(outing["project_id"])
    return json_response(outing)
