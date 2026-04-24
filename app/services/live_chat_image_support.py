from __future__ import annotations

import base64
import binascii
import os
from datetime import datetime

from . import live_chat_prompt_support as prompt_support


def generate_japanese_conversation_image_prompt(text_ai_client, context: dict, state: dict) -> dict:
    prompt = prompt_support.build_japanese_conversation_image_prompt_request(context, state)
    try:
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("japanese image prompt response is invalid")
        prompt_ja = str(parsed.get("prompt_ja") or "").strip()
        if not prompt_ja:
            raise RuntimeError("japanese image prompt is empty")
        parsed["prompt_ja"] = prompt_ja
        parsed["scene_summary"] = str(parsed.get("scene_summary") or "").strip()
        parsed["focus_subjects"] = [str(item).strip() for item in (parsed.get("focus_subjects") or []) if str(item).strip()]
        return parsed
    except Exception:
        return prompt_support.fallback_japanese_conversation_image_prompt(context, state)


def resolve_active_characters(context: dict, state_json: dict, conversation_prompt: dict) -> list[dict]:
    focus_subjects = {str(name).strip() for name in (conversation_prompt.get("focus_subjects") or []) if str(name).strip()}
    active_characters = [item for item in context["characters"] if item["name"] in focus_subjects]
    if active_characters:
        return active_characters
    active_ids = state_json.get("active_character_ids") or [item["id"] for item in context["characters"]]
    active_characters = [item for item in context["characters"] if item["id"] in set(active_ids)]
    if active_characters:
        return active_characters
    return context["characters"]


def collect_reference_assets(characters: list[dict], *, limit: int = 2) -> tuple[list[str], list[int]]:
    reference_paths = []
    reference_asset_ids = []
    for character in characters[:limit]:
        base_asset = character.get("base_asset")
        if not base_asset or not base_asset.get("file_path"):
            continue
        reference_paths.append(base_asset["file_path"])
        reference_asset_ids.append(base_asset["id"])
    return reference_paths, reference_asset_ids


def store_generated_image(*, storage_root: str, project_id: int, session_id: int, image_base64: str) -> tuple[str, str, int]:
    try:
        raw_bytes = base64.b64decode(image_base64)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError("generated image payload is invalid") from exc
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    directory = os.path.join(
        storage_root,
        "projects",
        str(project_id),
        "generated",
        "live_chat",
        str(session_id),
    )
    os.makedirs(directory, exist_ok=True)
    file_name = f"live_chat_{timestamp}.png"
    file_path = os.path.join(directory, file_name)
    with open(file_path, "wb") as file_handle:
        file_handle.write(raw_bytes)
    return file_name, file_path, len(raw_bytes)
