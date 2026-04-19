import json

from typing import Any

STYLE_LOCK_SEGMENTS = [
    "visual novel CG",
    "consistent art style across scenes",
    "consistent character design",
    "consistent line art",
    "consistent coloring",
    "single cohesive illustration",
]

TEXT_BLOCK_SEGMENTS = [
    "no text",
    "no letters",
    "no words",
    "no subtitles",
    "no captions",
    "no speech bubbles",
    "no UI overlay",
    "no watermark",
    "no logo",
]

SHOT_FOCUS_SEGMENTS = [
    "single key story moment",
    "focused scene composition",
    "not a group shot",
    "no ensemble cast",
    "focus on the active speakers only",
]


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


def _split_narration_segments(value: Any) -> list[str]:
    text = _normalize_text(value)
    if not text:
        return []
    normalized = text.replace("\r\n", "\n")
    raw_segments = [segment.strip() for segment in normalized.split("\n\n")]
    segments = [segment.replace("\n", " ") for segment in raw_segments if segment]
    return segments


def _dialogue_items(value: Any) -> list[dict[str, str]]:
    loaded = _loads_jsonish(value)
    if not isinstance(loaded, list):
        return []
    items = []
    for row in loaded:
        if not isinstance(row, dict):
            continue
        speaker = _normalize_text(row.get("speaker") or row.get("speaker_name"))
        text = _normalize_text(row.get("text"))
        if not speaker and not text:
            continue
        items.append({"speaker": speaker, "text": text})
    return items


def _select_visual_characters(characters: list[Any], dialogue_items: list[dict[str, str]]) -> list[Any]:
    if not characters:
        return []
    dialogue_speakers = []
    seen_names = set()
    for item in reversed(dialogue_items):
        speaker = item.get("speaker", "")
        if not speaker or speaker in seen_names:
            continue
        seen_names.add(speaker)
        dialogue_speakers.append(speaker)
        if len(dialogue_speakers) >= 2:
            break
    selected = []
    if dialogue_speakers:
        for speaker in reversed(dialogue_speakers):
            for character in characters:
                if _normalize_text(_read(character, "name")) == speaker:
                    selected.append(character)
                    break
    if not selected:
        selected = list(characters[:2])
    return selected[:2]


def _build_story_moment(scene: Any, scene_state: dict[str, Any], dialogue_items: list[dict[str, str]]) -> str:
    narration_segments = _split_narration_segments(_read(scene, "narration_text"))
    summary = _normalize_text(_read(scene, "summary"))
    story_parts = []
    if narration_segments:
        story_parts.append(narration_segments[0])
    elif summary:
        story_parts.append(summary)

    event_type = _normalize_text(_read(scene_state, "event_type"))
    mood = _normalize_text(_read(scene_state, "mood"))
    if event_type:
        story_parts.append(f"event: {event_type}")
    if mood:
        story_parts.append(f"mood: {mood}")

    recent_lines = []
    for item in dialogue_items[-3:]:
        speaker = item.get("speaker", "")
        text = item.get("text", "")
        if speaker and text:
            recent_lines.append(f"{speaker} says {text}")
        elif text:
            recent_lines.append(text)
    if recent_lines:
        story_parts.append("dialogue beat: " + " / ".join(recent_lines))

    return ", ".join(part for part in story_parts if part)


def _build_character_segment(character: Any) -> str:
    name = _normalize_text(_read(character, "name"))
    role = _normalize_text(_read(character, "role"))
    appearance = _normalize_text(_read(character, "appearance_summary"))
    fragments = []
    if name:
        fragments.append(name)
    if role:
        fragments.append(role)
    if appearance:
        fragments.append(appearance)
    return ", ".join(fragments)


def _extract_style_profile(project: Any, world: Any, image_rule: Any) -> str:
    project_settings = _loads_jsonish(_read(project, "settings_json")) or {}
    candidates = [
        _read(project_settings, "art_style_profile"),
        _read(project_settings, "visual_style"),
        _read(project_settings, "image_style"),
        _read(image_rule, "style_rule"),
        _read(world, "tone"),
    ]
    for value in candidates:
        text = _normalize_text(value)
        if text:
            return text
    return ""


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
    dialogue_items = _dialogue_items(_read(scene, "dialogue_json"))
    visual_characters = _select_visual_characters(characters, dialogue_items)
    visual_character_names = [
        _normalize_text(_read(character, "name"))
        for character in visual_characters
        if _normalize_text(_read(character, "name"))
    ]

    parts: list[str] = []

    parts.extend(STYLE_LOCK_SEGMENTS)
    parts.extend(SHOT_FOCUS_SEGMENTS)
    _append(parts, _read(image_rule, "prompt_prefix"))
    _append(parts, _extract_style_profile(project, world, image_rule))
    _append(parts, _build_story_moment(scene, scene_state, dialogue_items))
    if visual_character_names:
        _append(parts, f"focus characters: {', '.join(visual_character_names)}")
        if len(visual_character_names) == 1:
            _append(parts, "single character shot")
        elif len(visual_character_names) == 2:
            _append(parts, "two character conversation shot")

    if visual_characters:
        for character in visual_characters:
            segment = _build_character_segment(character)
            if segment:
                parts.append(segment)

    _append(parts, _read(image_rule, "hair_rule"))
    _append(parts, _read(image_rule, "face_rule"))
    _append(parts, _read(image_rule, "ear_rule"))
    _append(parts, _read(image_rule, "accessory_rule"))
    _append(parts, _read(image_rule, "outfit_rule"))

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
    _append(parts, _read(project, "genre"))
    parts.extend(TEXT_BLOCK_SEGMENTS)

    prompt = ", ".join(part for part in parts if part)
    prompt = " ".join(prompt.split())

    if not prompt:
        raise ValueError("insufficient context to build image prompt")

    suffix = _normalize_text(_read(image_rule, "prompt_suffix"))
    if suffix:
        prompt = f"{prompt}, {suffix}"

    negative_rule = _normalize_text(_read(image_rule, "negative_rule"))
    if negative_rule:
        prompt = f"{prompt}\n\nNegative prompt: {negative_rule}, group shot, crowd of characters, ensemble cast, unrelated extra characters"
    else:
        prompt = f"{prompt}\n\nNegative prompt: group shot, crowd of characters, ensemble cast, unrelated extra characters"

    return prompt
