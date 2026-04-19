import json
from typing import Any


DEFAULT_SCENE_OUTPUT_SCHEMA = {
    "title": "scene title",
    "summary": "short scene summary",
    "narration_text": "narration text",
    "dialogues": [{"speaker": "character name", "text": "dialogue line"}],
    "choices": [{"choice_text": "choice text", "next_scene_hint": "optional next scene hint"}],
}

DEFAULT_STATE_OUTPUT_SCHEMA = {
    "location": "place name",
    "time_of_day": "day or night",
    "lighting": "lighting description",
    "mood": "scene mood",
    "camera": "camera composition",
    "character_expression": "main expression",
    "character_pose": "main pose",
    "background": "background description",
    "event_type": "guidance, battle, conversation, exploration, etc.",
}


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


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value).strip()


def _lines_from_list(title: str, values: list[str]) -> list[str]:
    rows = [value for value in values if value]
    if not rows:
        return [f"{title}: none"]
    return [f"{title}:", *[f"- {value}" for value in rows]]


def _format_character(character: Any) -> str:
    name = _read(character, "name", "unknown")
    fields = [
        ("role", _read(character, "role")),
        ("personality", _read(character, "personality")),
        ("first_person", _read(character, "first_person")),
        ("second_person", _read(character, "second_person")),
        ("speech_style", _read(character, "speech_style")),
        ("speech_sample", _read(character, "speech_sample")),
        ("ng_rules", _read(character, "ng_rules")),
        ("appearance", _read(character, "appearance_summary")),
    ]
    parts = [f"{label}: {_stringify(value)}" for label, value in fields if _stringify(value)]
    return f"{name} | " + " | ".join(parts) if parts else str(name)


def _format_glossary_term(term: Any) -> str:
    parts = [_read(term, "term", "unknown")]
    if _read(term, "reading"):
        parts.append(f"reading: {_stringify(_read(term, 'reading'))}")
    if _read(term, "category"):
        parts.append(f"category: {_stringify(_read(term, 'category'))}")
    if _read(term, "description"):
        parts.append(f"description: {_stringify(_read(term, 'description'))}")
    return " | ".join(parts)


def _format_recent_scene(scene: Any) -> str:
    dialogue_json = _loads_jsonish(_read(scene, "dialogue_json"))
    return " | ".join(
        filter(
            None,
            [
                f"id={_stringify(_read(scene, 'id'))}",
                f"title={_stringify(_read(scene, 'title'))}",
                f"summary={_stringify(_read(scene, 'summary'))}",
                f"narration={_stringify(_read(scene, 'narration_text'))}",
                f"dialogue={_stringify(dialogue_json)}",
            ],
        )
    )


def _format_story_memory(memory: Any) -> str:
    return " | ".join(
        filter(
            None,
            [
                f"type={_stringify(_read(memory, 'memory_type'))}",
                f"key={_stringify(_read(memory, 'memory_key'))}",
                f"importance={_stringify(_read(memory, 'importance'))}",
                _stringify(_read(memory, "content_text")),
            ],
        )
    )


def _build_scene_generation_prompt(context: dict[str, Any]) -> str:
    project = _read(context, "project", {})
    world = _read(context, "world", {})
    story_outline = _read(context, "story_outline", {})
    scene = _read(context, "scene", {})
    chapter = _read(context, "chapter", {})
    previous_scene = _read(context, "previous_scene")
    recent_scenes = list(_read(context, "recent_scenes", []) or [])
    story_memories = list(_read(context, "story_memories", []) or [])
    characters = list(_read(context, "characters", []) or [])
    glossary_terms = list(_read(context, "glossary_terms", []) or [])
    extra_instruction = _read(context, "instruction") or _read(context, "extra_instruction")
    choice_count = _read(context, "choice_count")

    world_rules = _loads_jsonish(_read(world, "rules_json"))
    forbidden_rules = _loads_jsonish(_read(world, "forbidden_json"))
    outline_json = _loads_jsonish(_read(story_outline, "outline_json"))
    current_dialogues = _loads_jsonish(_read(scene, "dialogue_json"))
    current_state = _loads_jsonish(_read(scene, "scene_state_json"))

    lines = [
        "あなたは日本語のノベルゲーム制作アシスタントです。",
        "以下の設定、過去文脈、重要メモを踏まえて、次に使える1シーン分の本文を生成してください。",
        "",
        "出力ルール:",
        "- 必ず JSON オブジェクトのみを返してください。",
        "- 地の文、会話、選択肢を含めてください。",
        "- キャラクターの口調と世界観の整合性を守ってください。",
        "- 重要メモにある内容は矛盾なく引き継いでください。",
        "- プレイヤー名や固有名詞が出ている場合は必ず維持してください。",
        "",
        "出力JSONスキーマ:",
        json.dumps(DEFAULT_SCENE_OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
        "",
        "project:",
        f"- title: {_stringify(_read(project, 'title')) or 'none'}",
        f"- genre: {_stringify(_read(project, 'genre')) or 'none'}",
        f"- summary: {_stringify(_read(project, 'summary')) or 'none'}",
        f"- project_type: {_stringify(_read(project, 'project_type')) or 'none'}",
        "",
        "chapter:",
        f"- chapter_no: {_stringify(_read(chapter, 'chapter_no')) or 'none'}",
        f"- title: {_stringify(_read(chapter, 'title')) or 'none'}",
        f"- summary: {_stringify(_read(chapter, 'summary')) or 'none'}",
        f"- objective: {_stringify(_read(chapter, 'objective')) or 'none'}",
        "",
        "world:",
        f"- name: {_stringify(_read(world, 'name')) or 'none'}",
        f"- era_description: {_stringify(_read(world, 'era_description')) or 'none'}",
        f"- technology_level: {_stringify(_read(world, 'technology_level')) or 'none'}",
        f"- social_structure: {_stringify(_read(world, 'social_structure')) or 'none'}",
        f"- tone: {_stringify(_read(world, 'tone')) or 'none'}",
        f"- overview: {_stringify(_read(world, 'overview')) or 'none'}",
        f"- rules_json: {_stringify(world_rules) or 'none'}",
        f"- forbidden_json: {_stringify(forbidden_rules) or 'none'}",
        "",
        "story_outline:",
        f"- premise: {_stringify(_read(story_outline, 'premise')) or 'none'}",
        f"- protagonist_position: {_stringify(_read(story_outline, 'protagonist_position')) or 'none'}",
        f"- main_goal: {_stringify(_read(story_outline, 'main_goal')) or 'none'}",
        f"- branching_policy: {_stringify(_read(story_outline, 'branching_policy')) or 'none'}",
        f"- ending_policy: {_stringify(_read(story_outline, 'ending_policy')) or 'none'}",
        f"- outline_text: {_stringify(_read(story_outline, 'outline_text')) or 'none'}",
        f"- outline_json: {_stringify(outline_json) or 'none'}",
        "",
        "current_scene:",
        f"- id: {_stringify(_read(scene, 'id')) or 'none'}",
        f"- title: {_stringify(_read(scene, 'title')) or 'none'}",
        f"- summary: {_stringify(_read(scene, 'summary')) or 'none'}",
        f"- narration_text: {_stringify(_read(scene, 'narration_text')) or 'none'}",
        f"- dialogue_json: {_stringify(current_dialogues) or 'none'}",
        f"- scene_state_json: {_stringify(current_state) or 'none'}",
        f"- sort_order: {_stringify(_read(scene, 'sort_order')) or 'none'}",
        f"- is_fixed: {'true' if _read(scene, 'is_fixed') else 'false'}",
    ]

    if previous_scene is not None:
        lines.extend(
            [
                "",
                "previous_scene:",
                f"- title: {_stringify(_read(previous_scene, 'title')) or 'none'}",
                f"- summary: {_stringify(_read(previous_scene, 'summary')) or 'none'}",
                f"- narration_text: {_stringify(_read(previous_scene, 'narration_text')) or 'none'}",
                f"- dialogue_json: {_stringify(_loads_jsonish(_read(previous_scene, 'dialogue_json'))) or 'none'}",
            ]
        )

    lines.extend(["", *(_lines_from_list("recent_scenes_in_chapter", [_format_recent_scene(item) for item in recent_scenes]))])
    lines.extend(["", *(_lines_from_list("story_memories", [_format_story_memory(item) for item in story_memories]))])
    lines.extend(["", *(_lines_from_list("characters", [_format_character(character) for character in characters]))])
    lines.extend(["", *(_lines_from_list("glossary_terms", [_format_glossary_term(term) for term in glossary_terms]))])

    if choice_count is not None:
        lines.extend(["", f"choice_count: {choice_count}"])
    if extra_instruction:
        lines.extend(["", f"extra_instruction: {_stringify(extra_instruction)}"])

    lines.extend(
        [
            "",
            "追加指示:",
            "- 出力は自然な日本語にしてください。",
            "- dialogue の speaker は既存キャラクター名を優先してください。",
            "- recent_scenes_in_chapter と story_memories の情報は継続文脈として扱ってください。",
            "- 設定が足りない場合でも、既存情報と矛盾しない範囲で補完してください。",
        ]
    )
    return "\n".join(lines)


def _build_state_extraction_prompt(context: dict[str, Any]) -> str:
    project = _read(context, "project", {})
    world = _read(context, "world", {})
    scene = _read(context, "scene", {})
    recent_scenes = list(_read(context, "recent_scenes", []) or [])
    story_memories = list(_read(context, "story_memories", []) or [])
    characters = list(_read(context, "characters", []) or [])
    current_dialogues = _loads_jsonish(_read(scene, "dialogue_json"))

    lines = [
        "あなたはノベルゲーム用の状態抽出アシスタントです。",
        "本文から画像生成に必要なシーン状態だけを JSON で抽出してください。",
        "",
        "抽出ルール:",
        "- 必ず JSON オブジェクトのみを返してください。",
        "- scene_state として画像生成に必要な内容だけを含めてください。",
        "- recent_scenes と story_memories にある継続情報も踏まえてください。",
        "- プレイヤー名や重要固有名詞が scene_state に必要なら維持してください。",
        "",
        "出力JSONスキーマ:",
        json.dumps(DEFAULT_STATE_OUTPUT_SCHEMA, ensure_ascii=False, indent=2),
        "",
        "project:",
        f"- title: {_stringify(_read(project, 'title')) or 'none'}",
        f"- genre: {_stringify(_read(project, 'genre')) or 'none'}",
        "",
        "world:",
        f"- name: {_stringify(_read(world, 'name')) or 'none'}",
        f"- tone: {_stringify(_read(world, 'tone')) or 'none'}",
        f"- overview: {_stringify(_read(world, 'overview')) or 'none'}",
        "",
        *(_lines_from_list("characters", [_format_character(character) for character in characters])),
        "",
        *(_lines_from_list("recent_scenes_in_chapter", [_format_recent_scene(item) for item in recent_scenes])),
        "",
        *(_lines_from_list("story_memories", [_format_story_memory(item) for item in story_memories])),
        "",
        "target_scene:",
        f"- title: {_stringify(_read(scene, 'title')) or 'none'}",
        f"- summary: {_stringify(_read(scene, 'summary')) or 'none'}",
        f"- narration_text: {_stringify(_read(scene, 'narration_text')) or 'none'}",
        f"- dialogue_json: {_stringify(current_dialogues) or 'none'}",
    ]
    return "\n".join(lines)


def build_scene_prompt(context: dict[str, Any], *, mode: str = "scene_generation") -> str:
    if not isinstance(context, dict):
        raise ValueError("context must be a dict")
    if mode == "scene_generation":
        return _build_scene_generation_prompt(context)
    if mode == "state_extraction":
        return _build_state_extraction_prompt(context)
    raise ValueError("mode must be 'scene_generation' or 'state_extraction'")
