from flask import Blueprint, request

from ...api import json_response, serialize_datetime


story_outline_bp = Blueprint("story_outline", __name__)


def _serialize_story_outline(outline):
    if outline is None:
        return None
    return {
        "id": outline.id,
        "project_id": outline.project_id,
        "premise": outline.premise,
        "protagonist_name": outline.protagonist_name,
        "protagonist_position": outline.protagonist_position,
        "main_goal": outline.main_goal,
        "branching_policy": outline.branching_policy,
        "ending_policy": outline.ending_policy,
        "outline_text": outline.outline_text,
        "outline_json": outline.outline_json,
        "created_at": serialize_datetime(outline.created_at),
        "updated_at": serialize_datetime(outline.updated_at),
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
        "request_json": job.request_json,
        "response_json": job.response_json,
        "status": job.status,
        "started_at": serialize_datetime(job.started_at),
        "finished_at": serialize_datetime(job.finished_at),
        "error_message": job.error_message,
        "created_at": serialize_datetime(job.created_at),
        "updated_at": serialize_datetime(job.updated_at),
    }


@story_outline_bp.route("/projects/<int:project_id>/story-outline", methods=["GET"])
def get_story_outline(project_id: int):
    from ...services.story_outline_service import StoryOutlineService

    outline = StoryOutlineService().get_outline(project_id)
    return json_response(
        {
            "project_id": project_id,
            "story_outline": _serialize_story_outline(outline),
        }
    )


@story_outline_bp.route("/projects/<int:project_id>/story-outline", methods=["PUT"])
def upsert_story_outline(project_id: int):
    from ...services.story_outline_service import StoryOutlineService

    payload = request.get_json(silent=True) or {}
    outline = StoryOutlineService().upsert_outline(project_id, payload)
    return json_response(
        {
            "project_id": project_id,
            "story_outline": _serialize_story_outline(outline),
        }
    )


@story_outline_bp.route("/projects/<int:project_id>/story-outline/generate", methods=["POST"])
def generate_story_outline(project_id: int):
    from ...services.story_outline_service import StoryOutlineService

    payload = request.get_json(silent=True) or {}
    service = StoryOutlineService()
    try:
        job = service.generate_outline(project_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except RuntimeError as exc:
        return json_response({"message": str(exc)}, status=502)
    outline = service.get_outline(project_id)
    return json_response(
        {
            "project_id": project_id,
            "job": _serialize_generation_job(job),
            "story_outline": _serialize_story_outline(outline),
        },
    )
