import json

from typing import Any


def _read(source: Any, key: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _loads_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _append(parts: list[str], value: Any) -> None:
    text = _normalize_text(value)
    if text:
        parts.append(text)


def _build_character_segment(character: Any) -> str:
    name = _normalize_text(_read(character, "name"))
    role = _normalize_text(_read(character, "role"))
    appearance = _normalize_text(_read(character, "appearance_summary"))
    personality = _normalize_text(_read(character, "personality"))
    speech_style = _normalize_text(_read(character, "speech_style"))
    fragments = []
    if name:
        fragments.append(name)
    if role:
        fragments.append(role)
    if appearance:
        fragments.append(appearance)
    if personality:
        fragments.append(f"personality hint: {personality}")
    if speech_style:
        fragments.append(f"tone hint: {speech_style}")
    return ", ".join(fragments)


def build_image_prompt(context: dict) -> str:
    if not isinstance(context, dict):
        raise ValueError("context must be a dict")

    scene = _read(context, "scene", {})
    world = _read(context, "world", {})
    project = _read(context, "project", {})
    characters = list(_read(context, "characters", []) or [])
    image_rule = _read(context, "image_rule", {}) or {}
    scene_state = _loads_jsonish(_read(context, "scene_state"))
    if scene_state is None:
        scene_state = _loads_jsonish(_read(scene, "scene_state_json")) or {}

    parts: list[str] = []

    _append(parts, _read(image_rule, "prompt_prefix"))

    if characters:
        for character in characters:
            segment = _build_character_segment(character)
            if segment:
                parts.append(segment)

    _append(parts, _read(image_rule, "hair_rule"))
    _append(parts, _read(image_rule, "face_rule"))
    _append(parts, _read(image_rule, "ear_rule"))
    _append(parts, _read(image_rule, "accessory_rule"))
    _append(parts, _read(image_rule, "outfit_rule"))
    _append(parts, _read(image_rule, "style_rule"))

    _append(parts, _read(scene_state, "character_expression"))
    _append(parts, _read(scene_state, "noa_expression"))
    _append(parts, _read(scene_state, "character_pose"))
    _append(parts, _read(scene_state, "noa_pose"))
    _append(parts, _read(scene_state, "location"))
    _append(parts, _read(scene_state, "background"))
    _append(parts, _read(scene_state, "time_of_day"))
    _append(parts, _read(scene_state, "lighting"))
    _append(parts, _read(scene_state, "mood"))
    _append(parts, _read(scene_state, "camera"))
    _append(parts, _read(scene_state, "event_type"))

    _append(parts, _read(world, "name"))
    _append(parts, _read(world, "tone"))
    _append(parts, _read(world, "overview"))
    _append(parts, _read(project, "genre"))
    _append(parts, _read(scene, "summary"))

    prompt = ", ".join(part for part in parts if part)
    prompt = " ".join(prompt.split())

    if not prompt:
        raise ValueError("insufficient context to build image prompt")

    suffix = _normalize_text(_read(image_rule, "prompt_suffix"))
    if suffix:
        prompt = f"{prompt}, {suffix}"

    negative_rule = _normalize_text(_read(image_rule, "negative_rule"))
    if negative_rule:
        prompt = f"{prompt}\n\nNegative prompt: {negative_rule}"

    return prompt
