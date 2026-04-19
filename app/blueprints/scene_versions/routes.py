from flask import Blueprint

from ...api import json_response
from ...services.scene_version_service import SceneVersionService


scene_versions_bp = Blueprint("scene_versions", __name__)
scene_version_service = SceneVersionService()
def _serialize_scene_version(version):
    if version is None:
        return None
    return {
        "id": version.id,
        "scene_id": version.scene_id,
        "version_no": version.version_no,
        "source_type": version.source_type,
        "generated_by": version.generated_by,
        "narration_text": version.narration_text,
        "dialogue_json": version.dialogue_json,
        "choice_json": version.choice_json,
        "scene_state_json": version.scene_state_json,
        "image_prompt_text": version.image_prompt_text,
        "note_text": version.note_text,
        "is_adopted": bool(version.is_adopted),
        "created_at": version.created_at.isoformat() if getattr(version, "created_at", None) else None,
    }


@scene_versions_bp.route("/scenes/<int:scene_id>/versions", methods=["GET"])
def list_scene_versions(scene_id: int):
    versions = scene_version_service.list_versions(scene_id)
    data = [_serialize_scene_version(version) for version in versions]
    meta = {"scene_id": scene_id, "count": len(data)}
    return json_response(data, meta=meta)


@scene_versions_bp.route("/scenes/<int:scene_id>/versions/<int:version_id>/adopt", methods=["POST"])
def adopt_scene_version(scene_id: int, version_id: int):
    version = scene_version_service.adopt_version(scene_id, version_id)
    if not version:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_scene_version(version))
