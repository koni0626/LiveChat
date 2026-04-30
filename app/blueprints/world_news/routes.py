from flask import Blueprint, request

from ...api import NotFoundError, json_response
from ...services.world_news_service import WorldNewsService
from ..access import require_project_manage, require_project_view


world_news_bp = Blueprint("world_news", __name__)
world_news_service = WorldNewsService()


@world_news_bp.route("/projects/<int:project_id>/world-news", methods=["GET"])
def list_world_news(project_id: int):
    require_project_view(project_id)
    limit = int(request.args.get("limit") or 50)
    return json_response(world_news_service.list_news(project_id, limit=max(1, min(100, limit))))


@world_news_bp.route("/projects/<int:project_id>/world-news", methods=["POST"])
def create_world_news(project_id: int):
    _project, user = require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    return json_response(world_news_service.create_manual(project_id, user.id, payload), status=201)


@world_news_bp.route("/projects/<int:project_id>/world-news/generate", methods=["POST"])
def generate_world_news(project_id: int):
    _project, user = require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    return json_response(world_news_service.generate_manual(project_id, user.id, payload), status=201)


@world_news_bp.route("/projects/<int:project_id>/world-news/<int:news_id>", methods=["DELETE"])
def delete_world_news(project_id: int, news_id: int):
    require_project_manage(project_id)
    if not world_news_service.delete_news(project_id, news_id):
        raise NotFoundError()
    return json_response({"news_id": news_id, "deleted": True})
