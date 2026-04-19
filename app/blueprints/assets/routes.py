from flask import Blueprint, request

from ...api import json_response
from ...utils import json_util
from ...services.asset_service import AssetService
import os
from flask import current_app

assets_bp = Blueprint("assets", __name__)
asset_service = AssetService()
def _get_bool_query(name: str, default: bool = False) -> bool:
    value = request.args.get(name)
    if value is None:
        return default
    return str(value).lower() in {"1", "true", "yes", "on"}


def _serialize_asset(asset):
    if asset is None:
        return None
    metadata = asset.metadata_json
    parsed_metadata = None
    if metadata:
        try:
            parsed_metadata = json_util.loads(metadata)
        except Exception:
            parsed_metadata = metadata
    return {
        "id": asset.id,
        "project_id": asset.project_id,
        "asset_type": asset.asset_type,
        "file_name": asset.file_name,
        "file_path": asset.file_path,
        "media_url": _build_media_url(asset.file_path),
        "mime_type": asset.mime_type,
        "file_size": asset.file_size,
        "width": asset.width,
        "height": asset.height,
        "checksum": asset.checksum,
        "metadata_json": asset.metadata_json,
        "metadata": parsed_metadata,
        "created_at": asset.created_at.isoformat() if getattr(asset, "created_at", None) else None,
        "updated_at": asset.updated_at.isoformat() if getattr(asset, "updated_at", None) else None,
        "deleted_at": asset.deleted_at.isoformat() if getattr(asset, "deleted_at", None) else None,
    }


def _build_media_url(file_path: str | None):
    if not file_path:
        return None
    storage_root = current_app.config.get("STORAGE_ROOT")
    normalized_path = os.path.normpath(file_path)
    normalized_root = os.path.normpath(storage_root)
    if not normalized_path.startswith(normalized_root):
        return None
    relative = os.path.relpath(normalized_path, normalized_root).replace("\\", "/")
    return f"/media/{relative}"


def _build_asset_payload_from_request(project_id: int | None = None):
    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if project_id is not None:
            payload.setdefault("project_id", project_id)
        return payload

    payload = dict(request.form)
    upload_file = request.files.get("file")
    if upload_file:
        payload["upload_file"] = upload_file
        payload.setdefault("file_name", upload_file.filename)
        payload.setdefault("file_path", upload_file.filename)
        payload.setdefault("mime_type", upload_file.mimetype)
        try:
            current_position = upload_file.stream.tell()
            upload_file.stream.seek(0, 2)
            payload.setdefault("file_size", upload_file.stream.tell())
            upload_file.stream.seek(current_position)
        except Exception:
            pass
    if project_id is not None:
        payload.setdefault("project_id", project_id)
    return payload


@assets_bp.route("/projects/<int:project_id>/assets", methods=["GET"])
def list_assets(project_id: int):
    include_deleted = _get_bool_query("include_deleted", default=False)
    asset_type = request.args.get("asset_type")
    search = request.args.get("q") or request.args.get("search")
    assets = asset_service.list_assets(project_id, include_deleted=include_deleted, asset_type=asset_type)
    if search:
        keyword = search.strip().lower()
        assets = [
            asset for asset in assets
            if keyword in (asset.file_name or "").lower()
            or keyword in (asset.mime_type or "").lower()
            or keyword in (asset.file_path or "").lower()
        ]
    data = [_serialize_asset(asset) for asset in assets]
    meta = {"project_id": project_id, "count": len(data)}
    if asset_type:
        meta["asset_type"] = asset_type
    if search:
        meta["search"] = search
    return json_response(data, meta=meta)


@assets_bp.route("/projects/<int:project_id>/assets", methods=["POST"])
def create_asset(project_id: int):
    payload = _build_asset_payload_from_request(project_id)
    try:
        asset = asset_service.create_asset(project_id, payload)
    except (KeyError, ValueError) as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_asset(asset), status=201)


@assets_bp.route("/assets/upload", methods=["POST"])
def upload_asset():
    payload = _build_asset_payload_from_request()
    project_id = payload.get("project_id")
    try:
        asset = asset_service.create_asset(project_id, payload)
    except (KeyError, ValueError) as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(_serialize_asset(asset), status=201)


@assets_bp.route("/assets/<int:asset_id>", methods=["GET"])
def get_asset(asset_id: int):
    include_deleted = _get_bool_query("include_deleted", default=False)
    asset = asset_service.get_asset(asset_id, include_deleted=include_deleted)
    if not asset:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_asset(asset))


@assets_bp.route("/assets/<int:asset_id>", methods=["PATCH"])
def update_asset(asset_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        asset = asset_service.update_asset(asset_id, payload)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    if not asset:
        return json_response({"message": "not_found"}, status=404)
    return json_response(_serialize_asset(asset))


@assets_bp.route("/assets/<int:asset_id>", methods=["DELETE"])
def delete_asset(asset_id: int):
    deleted = asset_service.delete_asset(asset_id)
    if not deleted:
        return json_response({"message": "not_found"}, status=404)
    return json_response({"asset_id": asset_id, "deleted": True})
