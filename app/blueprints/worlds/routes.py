from flask import Blueprint, request

from ...api import json_response, serialize_datetime
from ...services.glossary_service import GlossaryService


worlds_bp = Blueprint("worlds", __name__)
glossary_service = GlossaryService()


def _load_json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value
    value = value.strip()
    if not value:
        return None
    try:
        from ...utils import json_util
        return json_util.loads(value)
    except Exception:
        return value


def _serialize_world(world, project_id: int):
    if world is None:
        return {"project_id": project_id, "world": None}
    return {
        "project_id": project_id,
        "world": {
            "id": world.id,
            "project_id": world.project_id,
            "name": world.name,
            "era_description": world.era_description,
            "technology_level": world.technology_level,
            "social_structure": world.social_structure,
            "tone": world.tone,
            "overview": world.overview,
            "rules_json": world.rules_json,
            "forbidden_json": world.forbidden_json,
            "ui_fields": {
                "world_name": world.name,
                "time_period": world.era_description,
                "place_description": world.overview,
                "technology_level": world.technology_level,
                "social_structure": world.social_structure,
                "world_tone": world.tone,
                "important_facilities": _load_json(world.rules_json),
                "forbidden_settings": _load_json(world.forbidden_json),
            },
            "created_at": serialize_datetime(world.created_at),
            "updated_at": serialize_datetime(world.updated_at),
        },
    }


@worlds_bp.route("/projects/<int:project_id>/world", methods=["GET"])
def get_world(project_id: int):
    from ...services.world_service import WorldService
    world = WorldService().get_world(project_id)
    return json_response(_serialize_world(world, project_id))


@worlds_bp.route("/projects/<int:project_id>/world", methods=["PUT"])
def put_world(project_id: int):
    from ...services.world_service import WorldService
    payload = request.get_json(silent=True) or {}
    world = WorldService().upsert_world(project_id, payload)
    return json_response(_serialize_world(world, project_id))


@worlds_bp.route("/projects/<int:project_id>/world-context", methods=["GET"])
def get_world_context(project_id: int):
    from ...services.world_service import WorldService

    world = WorldService().get_world(project_id)
    glossary_terms = glossary_service.list_terms(project_id)
    categories = sorted({term.category for term in glossary_terms if term.category})
    return json_response(
        {
            **_serialize_world(world, project_id),
            "glossary_terms": [
                {
                    "id": term.id,
                    "term": term.term,
                    "reading": term.reading,
                    "description": term.description,
                    "category": term.category,
                }
                for term in glossary_terms
            ],
            "glossary_meta": {
                "count": len(glossary_terms),
                "categories": categories,
            },
        }
    )
