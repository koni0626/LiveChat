from datetime import datetime
from ..repositories.export_job_repository import ExportJobRepository
from ..utils import json_util

class ExportService:
    VALID_STATUSES = {"queued", "running", "success", "failed"}

    def __init__(self, repository: ExportJobRepository | None = None):
        self._repo = repository or ExportJobRepository()

    def _normalize_status(self, status: str):
        if not status:
            raise ValueError("status is required")
        if status not in self.VALID_STATUSES:
            raise ValueError(f"status must be one of {sorted(self.VALID_STATUSES)}")
        return status
    def _resolve_options_json(self, payload: dict) -> str | None:
        if "options_json" in payload and payload.get("options_json") is not None:
            return payload.get("options_json")
        if "include_images" in payload:
            return json_util.dumps({"include_images": bool(payload.get("include_images"))})
        return None
    def list_exports(self, project_id: int, limit: int | None = None):
        return self._repo.list_by_project(project_id, limit=limit)

    def create_export(self, project_id: int, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        export_type = payload.get("export_type")
        if not export_type:
            raise ValueError("export_type is required")
        options_json = self._resolve_options_json(payload)
        normalized = {
            "export_type": export_type,
            "asset_id": payload.get("asset_id"),
            "options_json": options_json,
            "status": self._normalize_status(payload.get("status") or "queued"),
            "started_at": payload.get("started_at"),
            "finished_at": payload.get("finished_at"),
            "error_message": payload.get("error_message"),
        }
        return self._repo.create(project_id, normalized)
    def get_export(self, export_job_id: int):
        return self._repo.get_by_id(export_job_id)

    def queue_export(
        self,
        project_id: int,
        export_type: str,
        *,
        asset_id: int | None = None,
        options_json: str | None = None,
        include_images: bool | None = None,
    ):
        if not export_type:
            raise ValueError("export_type is required")
        if options_json is None and include_images is not None:
            options_json = json_util.dumps({"include_images": bool(include_images)})
        payload = {
            "export_type": export_type,
            "asset_id": asset_id,
            "options_json": options_json,
            "status": "queued",
        }
        return self._repo.create(project_id, payload)

    def update_export(self, export_job_id: int, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        data = dict(payload)
        if "status" in data:
            data["status"] = self._normalize_status(data["status"])
        return self._repo.update(export_job_id, data)

    def mark_started(self, export_job_id: int):
        now = datetime.utcnow()
        return self._repo.update(
            export_job_id,
            {
                "status": "running",
                "started_at": now,
                "finished_at": None,
                "error_message": None,
            },
        )

    def mark_finished(
        self,
        export_job_id: int,
        *,
        asset_id: int | None = None,
        options_json: str | None = None,
    ):
        payload = {
            "status": "success",
            "finished_at": datetime.utcnow(),
        }
        if asset_id is not None:
            payload["asset_id"] = asset_id
        if options_json is not None:
            payload["options_json"] = options_json
        return self._repo.update(export_job_id, payload)

    def mark_failed(self, export_job_id: int, error_message: str):
        if not error_message:
            raise ValueError("error_message is required")
        return self._repo.update(
            export_job_id,
            {
                "status": "failed",
                "error_message": error_message,
                "finished_at": datetime.utcnow(),
            },
        )
