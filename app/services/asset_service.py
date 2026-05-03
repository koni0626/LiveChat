import hashlib
import io
import os
import uuid
from pathlib import Path

from flask import current_app
from PIL import Image
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
        file_bytes = upload_file.read()
        if not file_bytes:
            raise ValueError("file is required")
        image_info = self._validate_upload_file(file_bytes, upload_file.mimetype)
        file_ext = self._extension_for_mime_type(image_info.get("mime_type")) or file_ext.lower()
        stored_name = f"{file_root or 'upload'}_{uuid.uuid4().hex[:12]}{file_ext}"
        file_path = os.path.join(upload_directory, stored_name)

        with open(file_path, "wb") as file_handle:
            file_handle.write(file_bytes)

        normalized = dict(payload)
        normalized["file_name"] = original_name
        normalized["file_path"] = file_path
        normalized["mime_type"] = image_info.get("mime_type")
        normalized["file_size"] = len(file_bytes)
        normalized["checksum"] = hashlib.sha256(file_bytes).hexdigest()
        normalized["width"] = image_info.get("width")
        normalized["height"] = image_info.get("height")
        normalized.pop("upload_file", None)
        return normalized

    def _extension_for_mime_type(self, mime_type: str | None) -> str | None:
        return {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
        }.get(str(mime_type or "").split(";", 1)[0].strip().lower())

    def _validate_upload_file(self, file_bytes: bytes, mime_type: str | None):
        max_bytes = int(current_app.config.get("ASSET_MAX_UPLOAD_BYTES", 10 * 1024 * 1024))
        if len(file_bytes) > max_bytes:
            raise ValueError("file is too large")

        allowed_types = set(current_app.config.get("ASSET_ALLOWED_IMAGE_MIME_TYPES") or set())
        declared_mime = str(mime_type or "").split(";", 1)[0].strip().lower()

        try:
            with Image.open(io.BytesIO(file_bytes)) as image:
                width, height = image.size
                actual_mime = Image.MIME.get(image.format or "", declared_mime)
                actual_mime = str(actual_mime or "").split(";", 1)[0].strip().lower()
                if actual_mime not in allowed_types:
                    raise ValueError("unsupported image type")
                max_pixels = int(current_app.config.get("ASSET_MAX_IMAGE_PIXELS", 24_000_000))
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise ValueError("image dimensions are too large")
                image.verify()
        except Exception as exc:
            if isinstance(exc, ValueError):
                raise
            raise ValueError("invalid image file") from exc
        return {"width": width, "height": height, "mime_type": actual_mime}

    def _ensure_file_path_under_storage(self, payload: dict) -> dict:
        file_path = payload.get("file_path")
        if not file_path:
            return payload
        storage_root = Path(self._get_storage_root()).resolve()
        resolved_path = Path(str(file_path)).resolve()
        try:
            resolved_path.relative_to(storage_root)
        except ValueError as exc:
            raise ValueError("file_path must be under storage root") from exc
        normalized = dict(payload)
        normalized["file_path"] = str(resolved_path)
        return normalized

    def list_assets(self, project_id: int, include_deleted: bool = False, asset_type: str | None = None):
        return self._repo.list_by_project(
            project_id, include_deleted=include_deleted, asset_type=asset_type
        )

    def create_asset(self, project_id: int, payload: dict):
        project_id = int(project_id)
        normalized_payload = self._save_upload_file(project_id, payload)
        normalized_payload = self._ensure_file_path_under_storage(normalized_payload)
        return self._repo.create(project_id, normalized_payload)

    def get_asset(self, asset_id: int, include_deleted: bool = False):
        return self._repo.get(asset_id, include_deleted=include_deleted)

    def update_asset(self, asset_id: int, payload: dict):
        return self._repo.update(asset_id, payload)

    def delete_asset(self, asset_id: int):
        return self._repo.delete(asset_id)

    def restore_asset(self, asset_id: int):
        return self._repo.restore(asset_id)
