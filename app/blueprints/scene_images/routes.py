import os

from flask import Blueprint, current_app, request

from ...api import json_response
from ...services.asset_service import AssetService
from ...services.generation_service import GenerationService
from ...services.scene_image_service import SceneImageService
from ...services.scene_service import SceneService


scene_images_bp = Blueprint("scene_images", __name__)
scene_image_service = SceneImageService()
generation_service = GenerationService()
asset_service = AssetService()
scene_service = SceneService()


def _build_media_url(file_path: str | None):
    if not file_path:
        return None
    storage_root = current_app.config.get("STORAGE_ROOT")
    if not storage_root:
        return None
    normalized_path = os.path.normpath(file_path)
    normalized_root = os.path.normpath(storage_root)
    if not normalized_path.startswith(normalized_root):
        return None
    relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
    return f"/media/{relative}"


def _serialize_asset(asset):
    if asset is None:
        return None
    return {
        "id": asset.id,
        "asset_type": asset.asset_type,
        "file_name": asset.file_name,
        "file_path": asset.file_path,
        "mime_type": asset.mime_type,
        "file_size": asset.file_size,
        "width": asset.width,
        "height": asset.height,
        "media_url": _build_media_url(asset.file_path),
    }


def _serialize_scene_image(scene_image):
    if scene_image is None:
        return None
    asset = asset_service.get_asset(scene_image.asset_id)
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
        "asset": _serialize_asset(asset),
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


@scene_images_bp.route("/scenes/<int:scene_id>/images/upload", methods=["POST"])
def upload_scene_image(scene_id: int):
    scene = scene_service.get_scene(scene_id)
    if not scene:
        return json_response({"message": "not_found"}, status=404)

    upload_file = request.files.get("file")
    if upload_file is None:
        return json_response({"message": "file is required"}, status=400)

    quality = (request.form.get("quality") or "external").strip() or "external"
    size = (request.form.get("size") or "uploaded").strip() or "uploaded"
    image_type = (request.form.get("image_type") or "scene_full").strip() or "scene_full"
    is_selected = str(request.form.get("is_selected", "1")).lower() in {"1", "true", "yes", "on"}

    try:
        asset = asset_service.create_asset(
            scene.project_id,
            {
                "asset_type": "uploaded_scene_image",
                "upload_file": upload_file,
                "metadata_json": '{"source":"manual_upload"}',
            },
        )
        scene_image = scene_image_service.generate_scene_images(
            scene_id,
            {
                "asset_id": asset.id,
                "image_type": image_type,
                "prompt_text": request.form.get("prompt_text") or None,
                "state_json": scene.scene_state_json,
                "quality": quality,
                "size": size,
                "is_selected": 1 if is_selected else 0,
            },
        )
        if is_selected:
            scene_image = scene_image_service.select_scene_image(scene_image.id)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_scene_image(scene_image), status=201)


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
