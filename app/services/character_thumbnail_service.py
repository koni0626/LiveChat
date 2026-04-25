import os
from typing import Any

from flask import current_app
from PIL import Image

from ..clients.text_ai_client import TextAIClient
from ..services.asset_service import AssetService
from ..utils import json_util


class CharacterThumbnailService:
    THUMBNAIL_SIZE = 320

    def __init__(
        self,
        *,
        asset_service: AssetService | None = None,
        text_ai_client: TextAIClient | None = None,
    ):
        self._asset_service = asset_service or AssetService()
        self._text_ai_client = text_ai_client or TextAIClient()

    def generate_for_character(self, character):
        if not character or not getattr(character, "base_asset_id", None):
            return None
        base_asset = self._asset_service.get_asset(character.base_asset_id)
        if not base_asset or not base_asset.file_path or not os.path.exists(base_asset.file_path):
            return None

        with Image.open(base_asset.file_path) as image:
            image = image.convert("RGB")
            image_width, image_height = image.size
            face_box = self._estimate_face_box(base_asset.file_path, image_width, image_height)
            crop_box = self._build_crop_box(face_box, image_width, image_height)
            thumbnail = image.crop(crop_box)
            thumbnail.thumbnail((self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE), (8, 12, 24))
            offset = (
                (self.THUMBNAIL_SIZE - thumbnail.width) // 2,
                (self.THUMBNAIL_SIZE - thumbnail.height) // 2,
            )
            canvas.paste(thumbnail, offset)

            output_dir = self._build_output_directory(character.project_id)
            os.makedirs(output_dir, exist_ok=True)
            file_name = f"character_{character.id}_face_{character.base_asset_id}.png"
            file_path = os.path.join(output_dir, file_name)
            canvas.save(file_path, "PNG", optimize=True)

        file_size = os.path.getsize(file_path)
        asset = self._asset_service.create_asset(
            character.project_id,
            {
                "asset_type": "character_thumbnail",
                "file_name": file_name,
                "file_path": file_path,
                "mime_type": "image/png",
                "file_size": file_size,
                "width": self.THUMBNAIL_SIZE,
                "height": self.THUMBNAIL_SIZE,
                "metadata_json": json_util.dumps(
                    {
                        "source": "ai_face_crop",
                        "base_asset_id": base_asset.id,
                        "face_box": face_box,
                    }
                ),
            },
        )
        return asset

    def _build_output_directory(self, project_id: int) -> str:
        storage_root = current_app.config.get("STORAGE_ROOT")
        return os.path.join(storage_root, "projects", str(project_id), "assets", "character_thumbnail")

    def _estimate_face_box(self, file_path: str, image_width: int, image_height: int) -> dict[str, Any]:
        prompt = (
            "Return only JSON. Detect the primary character face in this image. "
            "This may be anime, illustration, or AI-generated art. "
            "Use the most important visible face when multiple faces exist. "
            "Return normalized coordinates from 0 to 1 using the original image bounds. "
            "Required keys: face_found, x, y, width, height, confidence, note. "
            "x and y are the top-left corner of the face bounding box. "
            "width and height are the face bounding box size. "
            "If the full face is not visible, estimate the head/face area. "
            "Do not include markdown."
        )
        try:
            result = self._text_ai_client.analyze_image(file_path, prompt=prompt)
        except Exception as exc:
            return self._fallback_face_box(image_width, image_height, reason=str(exc))

        parsed = result.get("parsed_json")
        if not isinstance(parsed, dict) or not parsed.get("face_found"):
            return self._fallback_face_box(image_width, image_height, reason="face_not_found")

        box = {
            "face_found": True,
            "x": self._coerce_ratio(parsed.get("x")),
            "y": self._coerce_ratio(parsed.get("y")),
            "width": self._coerce_ratio(parsed.get("width")),
            "height": self._coerce_ratio(parsed.get("height")),
            "confidence": self._coerce_ratio(parsed.get("confidence")),
            "note": str(parsed.get("note") or "")[:300],
        }
        if box["width"] <= 0.02 or box["height"] <= 0.02:
            return self._fallback_face_box(image_width, image_height, reason="invalid_face_box")
        return box

    def _fallback_face_box(self, image_width: int, image_height: int, *, reason: str) -> dict[str, Any]:
        size = min(image_width, image_height)
        return {
            "face_found": False,
            "x": ((image_width - size) / 2) / image_width,
            "y": ((image_height - size) / 2) / image_height,
            "width": size / image_width,
            "height": size / image_height,
            "confidence": 0,
            "note": f"fallback_center_crop: {reason}",
        }

    def _coerce_ratio(self, value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, number))

    def _build_crop_box(self, face_box: dict[str, Any], image_width: int, image_height: int) -> tuple[int, int, int, int]:
        x = face_box["x"] * image_width
        y = face_box["y"] * image_height
        width = face_box["width"] * image_width
        height = face_box["height"] * image_height
        center_x = x + width / 2
        center_y = y + height / 2
        side = max(width, height) * 2.35
        side = max(side, min(image_width, image_height) * 0.28)
        side = min(side, max(image_width, image_height))

        left = center_x - side / 2
        top = center_y - side * 0.46
        right = left + side
        bottom = top + side

        if left < 0:
            right -= left
            left = 0
        if top < 0:
            bottom -= top
            top = 0
        if right > image_width:
            left -= right - image_width
            right = image_width
        if bottom > image_height:
            top -= bottom - image_height
            bottom = image_height

        left = max(0, int(round(left)))
        top = max(0, int(round(top)))
        right = min(image_width, int(round(right)))
        bottom = min(image_height, int(round(bottom)))
        return left, top, right, bottom
