from flask import Blueprint, request

from ...api import json_response
from ...services.generation_service import GenerationService
from ...services.scene_image_service import SceneImageService


scene_images_bp = Blueprint("scene_images", __name__)
scene_image_service = SceneImageService()
generation_service = GenerationService()
def _serialize_scene_image(scene_image):
    if scene_image is None:
        return None
    return {
        "id": scene_image.id,
        "scene_id": scene_image.scene_id,
        "scene_version_id": scene_image.scene_version_id,
        "asset_id": scene_image.asset_id,
        "image_type": scene_image.image_type,
        "generation_job_id": scene_image.generation_job_id,
        "prompt_text": scene_image.prompt_text,
        "state_json": scene_image.state_json,
        "quality": scene_image.quality,
        "size": scene_image.size,
        "is_selected": bool(scene_image.is_selected),
        "created_at": scene_image.created_at.isoformat() if scene_image.created_at else None,
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


@scene_images_bp.route("/scenes/<int:scene_id>/images", methods=["GET"])
def list_scene_images(scene_id: int):
    items = scene_image_service.list_scene_images(scene_id)
    return json_response(
        [_serialize_scene_image(item) for item in items],
        meta={"scene_id": scene_id, "count": len(items)},
    )


@scene_images_bp.route("/scenes/<int:scene_id>/images/generate", methods=["POST"])
def generate_scene_images(scene_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        if payload.get("source_scene_image_id"):
            source_image = scene_image_service.get_scene_image(int(payload["source_scene_image_id"]))
            if not source_image or source_image.scene_id != scene_id:
                return json_response({"message": "not_found"}, status=404)
            payload.setdefault("target", source_image.image_type)
            payload.setdefault("size", source_image.size)
            payload.setdefault("quality", source_image.quality)

        job = generation_service.process_image_generation(scene_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    if not job:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_generation_job(job))


@scene_images_bp.route("/scene-images/<int:scene_image_id>/select", methods=["POST"])
def select_scene_image(scene_image_id: int):
    item = scene_image_service.select_scene_image(scene_image_id)
    if not item:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_scene_image(item))


@scene_images_bp.route("/scene-images/<int:scene_image_id>/regenerate", methods=["POST"])
def regenerate_scene_image(scene_image_id: int):
    source_image = scene_image_service.get_scene_image(scene_image_id)
    if not source_image:
        return json_response({"message": "not_found"}, status=404)

    payload = request.get_json(silent=True) or {}
    merged_payload = {
        "target": source_image.image_type,
        "size": source_image.size,
        "quality": source_image.quality,
    }
    merged_payload.update(payload)

    try:
        job = generation_service.process_image_generation(source_image.scene_id, merged_payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    if not job:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_generation_job(job))
