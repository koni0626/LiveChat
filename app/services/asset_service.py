import hashlib
import os
import uuid

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..repositories.asset_repository import AssetRepository


class AssetService:
    def __init__(self, repository: AssetRepository | None = None):
        self._repo = repository or AssetRepository()

    def _get_storage_root(self) -> str:
        try:
            return current_app.config.get("STORAGE_ROOT")
        except RuntimeError as exc:
            raise RuntimeError("STORAGE_ROOT is not configured") from exc

    def _build_upload_directory(self, project_id: int | None, asset_type: str) -> str:
        root = self._get_storage_root()
        project_segment = str(project_id) if project_id is not None else "common"
        return os.path.join(root, "projects", project_segment, "assets", asset_type)

    def _save_upload_file(self, project_id: int | None, payload: dict):
        upload_file = payload.get("upload_file")
        if not isinstance(upload_file, FileStorage):
            return payload

        asset_type = payload.get("asset_type") or "reference_image"
        upload_directory = self._build_upload_directory(project_id, asset_type)
        os.makedirs(upload_directory, exist_ok=True)

        original_name = secure_filename(upload_file.filename or "") or "upload.bin"
        file_root, file_ext = os.path.splitext(original_name)
        stored_name = f"{file_root or 'upload'}_{uuid.uuid4().hex[:12]}{file_ext}"
        file_path = os.path.join(upload_directory, stored_name)

        file_bytes = upload_file.read()
        if not file_bytes:
            raise ValueError("file is required")

        with open(file_path, "wb") as file_handle:
            file_handle.write(file_bytes)

        normalized = dict(payload)
        normalized["file_name"] = original_name
        normalized["file_path"] = file_path
        normalized["mime_type"] = normalized.get("mime_type") or upload_file.mimetype
        normalized["file_size"] = len(file_bytes)
        normalized["checksum"] = hashlib.sha256(file_bytes).hexdigest()
        normalized.pop("upload_file", None)
        return normalized

    def list_assets(self, project_id: int, include_deleted: bool = False, asset_type: str | None = None):
        return self._repo.list_by_project(
            project_id, include_deleted=include_deleted, asset_type=asset_type
        )

    def create_asset(self, project_id: int, payload: dict):
        normalized_payload = self._save_upload_file(project_id, payload)
        return self._repo.create(project_id, normalized_payload)

    def get_asset(self, asset_id: int, include_deleted: bool = False):
        return self._repo.get(asset_id, include_deleted=include_deleted)

    def update_asset(self, asset_id: int, payload: dict):
        return self._repo.update(asset_id, payload)

    def delete_asset(self, asset_id: int):
        return self._repo.delete(asset_id)

    def restore_asset(self, asset_id: int):
        return self._repo.restore(asset_id)
