from flask import Blueprint, request

from ...api import json_response
from ...models import World
from ..access import require_project_manage, require_project_view

from ...services.glossary_service import GlossaryService


glossary_bp = Blueprint("glossary", __name__)
glossary_service = GlossaryService()


def _require_term_manage(term_id: int, project_id: int | None = None):
    term = glossary_service.get_term(term_id, project_id=project_id)
    if not term:
        return None
    world = World.query.get(term.world_id)
    if not world:
        return None
    require_project_manage(world.project_id)
    return term


def _serialize_term(term):
    if term is None:
        return None
    return {
        "id": term.id,
        "world_id": term.world_id,
        "term": term.term,
        "reading": term.reading,
        "description": term.description,
        "category": term.category,
        "sort_order": term.sort_order,
        "created_at": term.created_at.isoformat() if term.created_at else None,
        "updated_at": term.updated_at.isoformat() if term.updated_at else None,
    }


@glossary_bp.route("/projects/<int:project_id>/glossary", methods=["GET"])
def list_glossary_terms(project_id: int):
    require_project_view(project_id)
    category = request.args.get("category")
    search = request.args.get("q") or request.args.get("search")
    terms = glossary_service.list_terms(project_id, category=category, search=search)
    data = [_serialize_term(term) for term in terms]
    categories = sorted({term.category for term in terms if term.category})
    meta = {"project_id": project_id, "total": len(data), "categories": categories}
    if search:
        meta["search"] = search
    return json_response(data, meta=meta)

@glossary_bp.route("/projects/<int:project_id>/glossary", methods=["POST"])
def create_glossary_term(project_id: int):
    require_project_manage(project_id)
    payload = request.get_json(silent=True) or {}
    try:
        term = glossary_service.create_term(project_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_term(term), status=201, meta={"project_id": project_id})

@glossary_bp.route("/glossary/<int:term_id>", methods=["PATCH"])
def update_glossary_term(term_id: int):
    payload = request.get_json(silent=True) or {}
    project_id = request.args.get("project_id", type=int)
    if not _require_term_manage(term_id, project_id=project_id):
        return json_response({"message": "not_found"}, status=404)
    try:
        term = glossary_service.update_term(term_id, payload, project_id=project_id)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not term:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_term(term))

@glossary_bp.route("/glossary/<int:term_id>", methods=["DELETE"])
def delete_glossary_term(term_id: int):
    project_id = request.args.get("project_id", type=int)
    if not _require_term_manage(term_id, project_id=project_id):
        return json_response({"message": "not_found"}, status=404)
    deleted = glossary_service.delete_term(term_id, project_id=project_id)
    if not deleted:
        return json_response({"message": "not_found"}, status=404)
    return json_response({"term_id": term_id, "deleted": True})
