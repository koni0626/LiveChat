import base64
import os
import uuid
from collections.abc import Sequence

from flask import current_app

from ..repositories.project_repository import ProjectRepository
from .asset_service import AssetService
from ..clients.image_ai_client import ImageAIClient
from ..utils import json_util

class ProjectService:
    VALID_STATUSES = {"draft", "published"}
    LEGACY_STATUS_MAP = {"active": "published", "archived": "draft"}

    def __init__(
        self,
        repository: ProjectRepository | None = None,
        asset_service: AssetService | None = None,
        image_ai_client: ImageAIClient | None = None,
    ):
        self._repo = repository or ProjectRepository()
        self._asset_service = asset_service or AssetService()
        self._image_ai_client = image_ai_client or ImageAIClient()

    def _normalize_status(self, status: str | None) -> str:
        value = str(status or "draft").strip() or "draft"
        value = self.LEGACY_STATUS_MAP.get(value, value)
        if value not in self.VALID_STATUSES:
            raise ValueError("status must be draft or published")
        return value

    def _apply_visibility_from_status(self, payload: dict) -> dict:
        status = self._normalize_status(payload.get("status"))
        visibility = "published" if status == "published" else "private"
        return {**payload, "status": status, "visibility": visibility, "chat_enabled": True}

    def list_projects(
        self,
        owner_user_id: int,
        *,
        include_deleted: bool = False,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ):
        return self._repo.list_by_owner(
            owner_user_id,
            include_deleted=include_deleted,
            statuses=statuses,
            search=search,
        )

    def list_all_projects(
        self,
        *,
        include_deleted: bool = False,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ):
        return self._repo.list_all(
            include_deleted=include_deleted,
            statuses=statuses,
            search=search,
        )

    def list_chat_available_projects(
        self,
        *,
        include_deleted: bool = False,
        statuses: Sequence[str] | None = None,
        search: str | None = None,
    ):
        return self._repo.list_chat_available(
            include_deleted=include_deleted,
            statuses=statuses,
            search=search,
        )

    def get_project(self, project_id: int, *, include_deleted: bool = False):
        return self._repo.get(project_id, include_deleted=include_deleted)

    def create_project(self, owner_user_id: int, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        if payload.get("title") in (None, ""):
            raise ValueError("title is required")
        payload = self._apply_visibility_from_status(payload)
        slug = payload.get("slug")
        if slug and self._repo.slug_exists(owner_user_id, slug):
            raise ValueError("slug_already_exists")
        return self._repo.create(owner_user_id, payload)

    def update_project(self, project_id: int, payload: dict):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a dict")
        project = self._repo.get(project_id, include_deleted=True)
        if not project or project.deleted_at is not None:
            return None
        if "status" in payload:
            payload = self._apply_visibility_from_status(payload)
        slug = payload.get("slug")
        if slug and self._repo.slug_exists(
            project.owner_user_id, slug, exclude_project_id=project.id
        ):
            raise ValueError("slug_already_exists")
        return self._repo.update(project_id, payload)

    def generate_signboard_image(self, project_id: int, payload: dict | None = None):
        project = self._repo.get(project_id)
        if not project:
            return None
        prompt = self._build_signboard_prompt(project)
        result = self._image_ai_client.generate_image(
            prompt,
            size="1536x1024",
            quality=(payload or {}).get("quality") or current_app.config.get("IMAGE_DEFAULT_QUALITY", "medium"),
            output_format="png",
            background="opaque",
        )
        file_name, file_path, file_size = self._store_generated_signboard_image(
            project_id=project_id,
            image_base64=result.get("image_base64"),
        )
        asset = self._asset_service.create_asset(
            project_id,
            {
                "project_id": project_id,
                "asset_type": "world_signboard",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "metadata_json": json_util.dumps({
                    "prompt": result.get("prompt") or prompt,
                    "model": result.get("model"),
                    "quality": result.get("quality"),
                    "size": "1536x1024",
                    "source": "world_setting",
                }),
            },
        )
        return self._repo.update(project_id, {"thumbnail_asset_id": asset.id})

    def _build_signboard_prompt(self, project) -> str:
        from .world_service import WorldService

        world = WorldService(project_service=self).get_world(project.id)
        lines = [
            "Create a 1536x1024 landscape key visual signboard image for a fictional live chat world.",
            "This image is used as the world/store entrance card, like a shop sign, title banner, or storefront key visual.",
            "Make the world concept understandable at a glance.",
            "A logo-like emblem or symbolic sign shape is welcome, but do not include readable text, letters, captions, or watermarks.",
            "Use a polished commercial key visual composition with a strong focal point, atmospheric lighting, and clear setting identity.",
            "Do not create a UI mockup. Create the actual signboard artwork.",
            f"World name: {project.title or ''}",
            f"World description: {project.summary or ''}",
        ]
        if world:
            lines.extend(
                [
                    f"Tone/style: {world.tone or ''}",
                    f"Era: {world.era_description or ''}",
                    f"Place/background: {world.overview or ''}",
                    f"Technology level: {world.technology_level or ''}",
                    f"Social structure: {world.social_structure or ''}",
                    f"Important facilities/rules: {world.rules_json or ''}",
                    f"Forbidden settings to avoid: {world.forbidden_json or ''}",
                ]
            )
        return "\n".join(lines)

    def _store_generated_signboard_image(self, *, project_id: int, image_base64: str | None):
        if not image_base64:
            raise RuntimeError("generated image payload is invalid")
        try:
            image_bytes = base64.b64decode(image_base64)
        except Exception as exc:
            raise RuntimeError("generated image payload is invalid") from exc
        storage_root = current_app.config.get("STORAGE_ROOT")
        directory = os.path.join(storage_root, "projects", str(project_id), "assets", "world_signboard")
        os.makedirs(directory, exist_ok=True)
        file_name = f"world_signboard_{uuid.uuid4().hex[:12]}.png"
        file_path = os.path.join(directory, file_name)
        with open(file_path, "wb") as file_handle:
            file_handle.write(image_bytes)
        return file_name, file_path, len(image_bytes)

    def delete_project(self, project_id: int):
        return self._repo.delete(project_id)

    def restore_project(self, project_id: int):
        return self._repo.restore(project_id)

    def slug_exists(
        self, owner_user_id: int, slug: str, *, exclude_project_id: int | None = None
    ) -> bool:
        return self._repo.slug_exists(
            owner_user_id, slug, exclude_project_id=exclude_project_id
        )
