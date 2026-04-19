from flask import Blueprint, request

from ...api import json_response, serialize_datetime

from ...services.ending_condition_service import EndingConditionService


ending_conditions_bp = Blueprint("ending_conditions", __name__)
ending_condition_service = EndingConditionService()


def _serialize_ending_condition(ending_condition):
    if ending_condition is None:
        return None
    return {
        "id": ending_condition.id,
        "project_id": ending_condition.project_id,
        "ending_type": ending_condition.ending_type,
        "name": ending_condition.name,
        "condition_text": ending_condition.condition_text,
        "condition_json": ending_condition.condition_json,
        "priority": ending_condition.priority,
        "created_at": serialize_datetime(ending_condition.created_at),
        "updated_at": serialize_datetime(getattr(ending_condition, "updated_at", None)),
    }


@ending_conditions_bp.route(
    "/projects/<int:project_id>/ending-conditions", methods=["GET"]
)
def list_ending_conditions(project_id: int):
    items = ending_condition_service.list_ending_conditions(project_id)
    return json_response([_serialize_ending_condition(item) for item in items], meta={"project_id": project_id})


@ending_conditions_bp.route(
    "/projects/<int:project_id>/ending-conditions", methods=["POST"]
)
def create_ending_condition(project_id: int):
    payload = request.get_json(silent=True) or {}
    item = ending_condition_service.create_ending_condition(project_id, payload)
    return json_response(_serialize_ending_condition(item), status=201)


@ending_conditions_bp.route(
    "/ending-conditions/<int:ending_condition_id>", methods=["GET"]
)
def get_ending_condition(ending_condition_id: int):
    item = ending_condition_service.get_ending_condition(ending_condition_id)
    if not item:
        raise LookupError("not_found")
    return json_response(_serialize_ending_condition(item))


@ending_conditions_bp.route(
    "/ending-conditions/<int:ending_condition_id>", methods=["PATCH"]
)
def update_ending_condition(ending_condition_id: int):
    payload = request.get_json(silent=True) or {}
    item = ending_condition_service.update_ending_condition(ending_condition_id, payload)
    return json_response(_serialize_ending_condition(item))


@ending_conditions_bp.route(
    "/ending-conditions/<int:ending_condition_id>", methods=["DELETE"]
)
def delete_ending_condition(ending_condition_id: int):
    ending_condition_service.delete_ending_condition(ending_condition_id)
    return json_response({"ending_condition_id": ending_condition_id, "deleted": True})
