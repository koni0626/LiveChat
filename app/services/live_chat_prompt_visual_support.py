from __future__ import annotations


def active_characters(context: dict, state_json: dict) -> list[dict]:
    active_ids = state_json.get("active_character_ids") or [item["id"] for item in context["characters"]]
    scoped = [item for item in context["characters"] if item["id"] in set(active_ids)]
    return scoped or context["characters"]


def _load_jsonish(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            import json

            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def collect_visual_style(context: dict, state_json: dict | None = None) -> str:
    state_json = state_json if isinstance(state_json, dict) else (context.get("state", {}).get("state_json") or {})
    active = active_characters(context, state_json)
    style_parts = []
    project_settings = _load_jsonish((context.get("project") or {}).get("settings_json"))
    for key in ("art_style_profile", "visual_style", "image_style"):
        value = str(project_settings.get(key) or "").strip()
        if value:
            style_parts.append(value)
    for character in active:
        style = str(character.get("art_style") or "").strip()
        if style:
            style_parts.append(f"{character.get('name')}: {style}")
    normalized = []
    seen = set()
    for item in style_parts:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return " / ".join(normalized)


def apply_visual_style(prompt: str, context: dict) -> str:
    value = str(prompt or "").strip()
    style = collect_visual_style(context)
    reference_rule = (
        "参照画像・基準画像がある場合は、その画像の画風を最優先で維持する。"
        "線の太さ、塗り、色味、光の質感、肌や髪のレンダリング、顔立ち、キャラクターデザインの密度、"
        "3D/2D/実写寄りなどの表現方向を変えない。"
        "新しい場面や衣装を描く場合も、別作品の絵柄に寄せず、参照画像と同じ作家・同じシリーズの続きに見えるようにする。"
    )
    if not style:
        return f"{value}\n\n{reference_rule}"
    return f"{value}\n\n画風・スタイル指定: {style}\n{reference_rule}\nこの画風を優先し、以後のシーンでも線、塗り、色味、質感を一貫させる。"


def forbid_text_in_image(prompt: str) -> str:
    value = str(prompt or "").strip()
    rule = (
        "画像内には文字を一切入れない。セリフ、字幕、吹き出し、看板の読める文字、UI、ロゴ、透かし、"
        "日本語・英語・記号・擬音文字を描かない。セリフは画像外のテキストボックスで表示するため、"
        "絵の中には文章や文字情報を絶対に描写しない。no text, no words, no letters, no subtitles, "
        "no captions, no speech bubbles, no readable signs, no UI overlay, no watermark, no logo."
    )
    lowered = value.lower()
    if "no speech bubbles" in lowered and "画像内には文字を一切入れない" in value:
        return value
    return f"{value}\n\n{rule}"


def build_recent_conversation_excerpt_ja(messages: list[dict], limit: int = 6) -> str:
    lines = []
    for message in messages[-limit:]:
        speaker = message.get("speaker_name") or message.get("sender_type") or "話者"
        text = str(message.get("message_text") or "").strip()
        if not text:
            continue
        lines.append(f"{speaker}「{text[:140]}」")
    return "\n".join(lines)


def build_visual_state(context: dict, state: dict, *, prompt: str) -> dict:
    state_json = state.get("state_json") or {}
    line_visual_note = state_json.get("line_visual_note") or {}
    scene_progression = state_json.get("scene_progression") or {}
    active = active_characters(context, state_json)

    location = line_visual_note.get("location") or scene_progression.get("location") or state_json.get("location")
    background_details = (
        line_visual_note.get("background")
        or scene_progression.get("background")
        or state_json.get("background")
        or location
    )
    focus_object = line_visual_note.get("focus_object")
    camera = line_visual_note.get("camera") or state_json.get("camera")
    mood = state_json.get("mood")
    scene_summary = (
        line_visual_note.get("scene_moment")
        or scene_progression.get("focus_summary")
        or state_json.get("focus_summary")
    )
    visible_names = [item["name"] for item in active[:2]]

    contradiction_hints = []
    normalized_background = str(background_details or "")
    if "雑貨屋" in normalized_background:
        contradiction_hints.extend(["屋外", "港", "ビルの廊下", "通路"])
    elif "港" in normalized_background:
        contradiction_hints.extend(["雑貨屋の店内", "ビルの廊下"])
    elif "街" in normalized_background or "シティ" in normalized_background:
        contradiction_hints.extend(["雑貨屋の店内"])

    return {
        "location": location,
        "background_details": background_details,
        "visible_characters": visible_names,
        "focus_object": focus_object,
        "camera": camera,
        "mood": mood,
        "current_visual_summary": scene_summary,
        "last_image_prompt": prompt,
        "must_not_contradict": contradiction_hints,
    }


def build_japanese_conversation_image_prompt_request(context: dict, state: dict) -> str:
    state_json = state.get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    line_visual_note = state_json.get("line_visual_note") or {}
    conversation_director = state_json.get("conversation_director") or {}
    active = active_characters(context, state_json)
    visual_style = collect_visual_style(context, state_json)

    lines = [
        "あなたはノベルゲームのイベントCG演出担当です。",
        "直近の会話を読んで、この会話に合うドラマチックな一枚絵の画像生成プロンプトを日本語で作成してください。",
        "返答は JSON object のみです。",
        "キーは prompt_ja, scene_summary, focus_subjects の3つです。",
        "prompt_ja は画像生成APIにそのまま渡せる自然な日本語1段落にしてください。",
        "一人称視点で、プレイヤー自身は画像に描かないでください。",
        "会話の流れから現在の場所や背景は自動で読み取り、その場に合う背景を入れてください。",
        "基準画像のキャラクターの見た目は参照画像側で固定される前提なので、長い外見説明は不要です。",
        "セリフ全文の説明ではなく、『今この瞬間の印象的な一場面』としてまとめてください。",
        "ノベルゲームの魅力的なイベントCGらしく、背景・感情・構図が噛み合うようにしてください。",
        "ありがちな案内ポーズや、毎回同じ振り返り構図は避けてください。",
        "",
        f"作品名: {context['project'].get('title') or '無題'}",
        f"世界観: {context['world'].get('overview') or context['world'].get('name') or ''}",
        f"現在地のヒント: {line_visual_note.get('location') or scene_progression.get('location') or state_json.get('location') or ''}",
        f"背景のヒント: {line_visual_note.get('background') or scene_progression.get('background') or state_json.get('background') or ''}",
        f"場面要約: {line_visual_note.get('scene_moment') or scene_progression.get('focus_summary') or state_json.get('focus_summary') or ''}",
        f"感情トーン: {conversation_director.get('emotional_tone') or state_json.get('mood') or ''}",
        f"画風・スタイル指定: {visual_style}",
        "登場キャラクター:",
    ]
    world_map_context = (context.get("world_map") or {}).get("prompt_context")
    if world_map_context:
        lines.extend(["ワールドマップ登録施設:", world_map_context])
    for character in active[:20]:
        nickname = character.get("nickname")
        label = f"{character['name']} / あだ名: {nickname}" if nickname else character["name"]
        lines.append(f"- {label}")
    lines.extend(
        [
            "",
            "直近の会話:",
            build_recent_conversation_excerpt_ja(context["messages"]),
        ]
    )
    return "\n".join(lines)


def fallback_japanese_conversation_image_prompt(context: dict, state: dict) -> dict:
    state_json = state.get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    line_visual_note = state_json.get("line_visual_note") or {}
    active = active_characters(context, state_json)
    character_names = "、".join(item["name"] for item in active[:2]) or "キャラクター"
    scene_summary = line_visual_note.get("scene_moment") or scene_progression.get("focus_summary") or state_json.get("focus_summary") or "会話が進んでいる場面"
    location = line_visual_note.get("background") or line_visual_note.get("location") or scene_progression.get("background") or scene_progression.get("location") or state_json.get("background") or state_json.get("location")
    mood = state_json.get("mood") or "ドラマチック"
    camera = line_visual_note.get("camera") or state_json.get("camera") or "印象的なイベントCG構図"
    focus_object = line_visual_note.get("focus_object")
    visual_style = collect_visual_style(context, state_json)

    prompt_parts = [
        "この会話に合う、ドラマチックなノベルゲーム風イベントCGを生成してください。",
        "視点はプレイヤーの一人称視点です。プレイヤー自身は画像に描かないでください。",
        f"登場キャラクターは{character_names}です。",
        f"今この瞬間は「{scene_summary}」です。",
        f"雰囲気は{mood}です。",
        f"構図は{camera}にしてください。",
    ]
    if location:
        prompt_parts.append(f"会話内容に合う背景として「{location}」が自然に分かるように描いてください。")
    if focus_object:
        prompt_parts.append(f"画面の見せ場は「{focus_object}」です。")
    if visual_style:
        prompt_parts.append(f"画風・スタイル指定は「{visual_style}」。線、塗り、色味、質感を一貫させてください。")
    prompt_parts.append("印象的で魅力的な一枚絵にしてください。")
    prompt_ja = " ".join(prompt_parts)
    return {
        "prompt_ja": prompt_ja,
        "scene_summary": scene_summary,
        "focus_subjects": [item["name"] for item in active[:2]],
    }


def normalize_first_person_visual_prompt(prompt: str) -> str:
    value = str(prompt or "").strip()
    replacements = (
        ("Two humanoids", "A first-person view"),
        ("two humanoids", "a first-person view"),
        ("Two people", "A first-person view"),
        ("two people", "a first-person view"),
        ("Two characters", "A first-person view"),
        ("two characters", "a first-person view"),
        ("The player and", ""),
        ("the player and", ""),
        ("player character", "viewer"),
    )
    for source, target in replacements:
        value = value.replace(source, target)

    forbidden_fragments = (
        "third-person view",
        "third person view",
        "full body of the player",
        "show the player character",
        "the player walking with",
        "player visible in frame",
    )
    lowered = value.lower()
    if any(fragment in lowered for fragment in forbidden_fragments):
        value = f"first-person POV, viewer is the player, do not show the player character, {value}"

    pov_requirements = (
        "first-person pov",
        "viewer is the player",
        "do not show the player character",
    )
    lowered = value.lower()
    missing = [item for item in pov_requirements if item not in lowered]
    if missing:
        if any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in value):
            prefix = "プレイヤーの一人称視点、プレイヤー自身は画像に描かない"
        else:
            prefix = "first-person POV, viewer is the player, do not show the player character"
        value = f"{prefix}, {value}"
    return value
