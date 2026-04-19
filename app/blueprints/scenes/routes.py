from flask import Blueprint, request

from ...api import json_response
from ...services.generation_service import GenerationService
from ...services.scene_choice_service import SceneChoiceService
from ...services.scene_service import SceneService
from ...services.scene_workspace_service import SceneWorkspaceService
from ...utils import json_util


scenes_bp = Blueprint("scenes", __name__)
scene_service = SceneService()
scene_choice_service = SceneChoiceService()
generation_service = GenerationService()
scene_workspace_service = SceneWorkspaceService()

BOOLEAN_TRUE_VALUES = {"1", "true", "True", "yes", "on"}
def _get_bool_query(name: str, default: bool = False) -> bool:
    value = request.args.get(name)
    if value is None:
        return default
    return str(value).lower() in BOOLEAN_TRUE_VALUES


def _serialize_scene(scene, *, include_choices=False):
    if scene is None:
        return None
    payload = {
        "id": scene.id,
        "project_id": scene.project_id,
        "chapter_id": scene.chapter_id,
        "parent_scene_id": scene.parent_scene_id,
        "scene_key": scene.scene_key,
        "title": scene.title,
        "summary": scene.summary,
        "narration_text": scene.narration_text,
        "dialogue_json": scene.dialogue_json,
        "scene_state_json": scene.scene_state_json,
        "image_prompt_text": scene.image_prompt_text,
        "active_version_id": scene.active_version_id,
        "sort_order": scene.sort_order,
        "is_fixed": bool(scene.is_fixed),
        "created_at": scene.created_at.isoformat() if getattr(scene, "created_at", None) else None,
        "updated_at": scene.updated_at.isoformat() if getattr(scene, "updated_at", None) else None,
        "deleted_at": scene.deleted_at.isoformat() if getattr(scene, "deleted_at", None) else None,
    }
    if include_choices:
        choices = scene_choice_service.list_choices(scene.id)
        payload["choices"] = [_serialize_choice(choice) for choice in choices]
    return payload


def _serialize_choice(choice):
    if choice is None:
        return None
    return {
        "id": choice.id,
        "scene_id": choice.scene_id,
        "choice_text": choice.choice_text,
        "next_scene_id": choice.next_scene_id,
        "condition_json": choice.condition_json,
        "result_summary": choice.result_summary,
        "sort_order": choice.sort_order,
        "created_at": choice.created_at.isoformat() if getattr(choice, "created_at", None) else None,
        "updated_at": choice.updated_at.isoformat() if getattr(choice, "updated_at", None) else None,
    }


def _serialize_generation_job(job):
    if job is None:
        return None
    return {
        "id": job.id,
        "project_id": job.project_id,
        "job_type": job.job_type,
        "target_type": job.target_type,
        "target_id": job.target_id,
        "model_name": job.model_name,
        "status": job.status,
        "request_json": job.request_json,
        "response_json": job.response_json,
        "started_at": job.started_at.isoformat() if getattr(job, "started_at", None) else None,
        "finished_at": job.finished_at.isoformat() if getattr(job, "finished_at", None) else None,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if getattr(job, "created_at", None) else None,
    }


def _build_generation_payload(payload):
    payload = dict(payload or {})
    if "request_json" not in payload:
        payload["request_json"] = json_util.dumps(payload)
    return payload


@scenes_bp.route("/projects/<int:project_id>/scenes", methods=["GET"])
def list_scenes(project_id: int):
    include_deleted = _get_bool_query("include_deleted", default=False)
    chapter_id = request.args.get("chapter_id", type=int)
    include_choices = _get_bool_query("include_choices", default=False)

    if chapter_id:
        scenes = scene_service.list_scenes_by_chapter(chapter_id, include_deleted=include_deleted)
    else:
        scenes = scene_service.list_scenes(project_id, include_deleted=include_deleted)

    data = [_serialize_scene(scene, include_choices=include_choices) for scene in scenes]
    meta = {"project_id": project_id, "count": len(data)}
    return json_response(data, meta=meta)


@scenes_bp.route("/projects/<int:project_id>/scenes", methods=["POST"])
def create_scene(project_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        scene = scene_service.create_scene(project_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_scene(scene), status=201)


@scenes_bp.route("/scenes/<int:scene_id>", methods=["GET"])
def get_scene(scene_id: int):
    include_deleted = _get_bool_query("include_deleted", default=False)
    include_choices = _get_bool_query("include_choices", default=False)
    scene = scene_service.get_scene(scene_id, include_deleted=include_deleted)
    if not scene:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_scene(scene, include_choices=include_choices))


@scenes_bp.route("/scenes/<int:scene_id>/editor-context", methods=["GET"])
def get_scene_editor_context(scene_id: int):
    return json_response(scene_workspace_service.get_editor_context(scene_id))


@scenes_bp.route("/scenes/<int:scene_id>/image-context", methods=["GET"])
def get_scene_image_context(scene_id: int):
    return json_response(scene_workspace_service.get_image_context(scene_id))


@scenes_bp.route("/scenes/<int:scene_id>/preview", methods=["GET"])
def get_scene_preview(scene_id: int):
    return json_response(scene_workspace_service.get_preview(scene_id))


@scenes_bp.route("/scenes/<int:scene_id>", methods=["PATCH"])
def update_scene(scene_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        scene = scene_service.update_scene(scene_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not scene:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_scene(scene))


@scenes_bp.route("/scenes/<int:scene_id>", methods=["DELETE"])
def delete_scene(scene_id: int):
    deleted = scene_service.delete_scene(scene_id)
    if not deleted:
        return json_response({"message": "not_found"}, status=404)
    return json_response({"scene_id": scene_id, "deleted": True})


@scenes_bp.route("/scenes/<int:scene_id>/generate", methods=["POST"])
def generate_scene(scene_id: int):
    payload = _build_generation_payload(request.get_json(silent=True) or {})
    try:
        job = generation_service.process_scene_generation(scene_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    if not job:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_generation_job(job))


@scenes_bp.route("/scenes/<int:scene_id>/extract-state", methods=["POST"])
def extract_state(scene_id: int):
    payload = _build_generation_payload(request.get_json(silent=True) or {})
    try:
        job = generation_service.process_state_extraction(scene_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    if not job:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_generation_job(job))


@scenes_bp.route("/scenes/<int:scene_id>/fix", methods=["POST"])
def fix_scene(scene_id: int):
    scene = scene_service.fix_scene(scene_id)
    if not scene:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_scene(scene))


@scenes_bp.route("/scenes/<int:scene_id>/unfix", methods=["POST"])
def unfix_scene(scene_id: int):
    scene = scene_service.unfix_scene(scene_id)
    if not scene:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_scene(scene))


@scenes_bp.route("/scenes/<int:scene_id>/choices", methods=["GET"])
def list_scene_choices(scene_id: int):
    choices = scene_choice_service.list_choices(scene_id)
    data = [_serialize_choice(choice) for choice in choices]
    meta = {"scene_id": scene_id, "count": len(data)}
    return json_response(data, meta=meta)


@scenes_bp.route("/scenes/<int:scene_id>/choices", methods=["POST"])
def create_scene_choice(scene_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        choice = scene_choice_service.create_choice(scene_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_choice(choice), status=201)


@scenes_bp.route("/scene-choices/<int:choice_id>", methods=["PATCH"])
def update_scene_choice(choice_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        choice = scene_choice_service.update_choice(choice_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not choice:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_choice(choice))


@scenes_bp.route("/scene-choices/<int:choice_id>", methods=["DELETE"])
def delete_scene_choice(choice_id: int):
    deleted = scene_choice_service.delete_choice(choice_id)
    if not deleted:
        return json_response({"message": "not_found"}, status=404)
    return json_response({"choice_id": choice_id, "deleted": True})
