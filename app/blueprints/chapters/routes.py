from flask import Blueprint, request

from ...api import json_response
from ...services.chapter_service import ChapterService

chapters_bp = Blueprint("chapters", __name__)
chapter_service = ChapterService()
def _serialize_chapter(chapter):
    if chapter is None:
        return None
    return {
        "id": chapter.id,
        "project_id": chapter.project_id,
        "chapter_no": chapter.chapter_no,
        "title": chapter.title,
        "summary": chapter.summary,
        "objective": chapter.objective,
        "sort_order": chapter.sort_order,
        "created_at": chapter.created_at.isoformat() if getattr(chapter, "created_at", None) else None,
        "updated_at": chapter.updated_at.isoformat() if getattr(chapter, "updated_at", None) else None,
    }


@chapters_bp.route("/projects/<int:project_id>/chapters", methods=["GET"])
def list_chapters(project_id: int):
    chapters = chapter_service.list_chapters(project_id)
    data = [_serialize_chapter(chapter) for chapter in chapters]
    meta = {"project_id": project_id, "count": len(data)}
    return json_response(data, meta=meta)


@chapters_bp.route("/projects/<int:project_id>/chapters", methods=["POST"])
def create_chapter(project_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        chapter = chapter_service.create_chapter(project_id, payload)
    except (KeyError, ValueError) as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_chapter(chapter), status=201)


@chapters_bp.route("/chapters/<int:chapter_id>", methods=["PATCH"])
def update_chapter(chapter_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        chapter = chapter_service.update_chapter(chapter_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not chapter:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_chapter(chapter))


@chapters_bp.route("/chapters/<int:chapter_id>", methods=["DELETE"])
def delete_chapter(chapter_id: int):
    deleted = chapter_service.delete_chapter(chapter_id)
    if not deleted:
        return json_response({"message": "not_found"}, status=404)
    return json_response({"chapter_id": chapter_id, "deleted": True})
