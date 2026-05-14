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



def collect_world_visual_context(context: dict) -> str:
    world = context.get("world") or {}
    parts = []
    labels = (
        ("World name", "name"),
        ("Tone", "tone"),
        ("Era", "era_description"),
        ("Place", "overview"),
        ("Technology", "technology_level"),
        ("Society", "social_structure"),
        ("Important facilities and visual rules", "rules_json"),
    )
    for label, key in labels:
        value = str(world.get(key) or "").strip()
        if value:
            parts.append(f"{label}: {value[:900]}")
    return "\n".join(parts)


def world_has_cyber_direction(context: dict) -> bool:
    world = context.get("world") or {}
    world_text = " ".join(
        str(world.get(key) or "")
        for key in (
            "name",
            "overview",
            "tone",
            "era_description",
            "technology_level",
            "social_structure",
            "rules_json",
        )
    ).lower()
    markers = (
        "cyber",
        "\u30b5\u30a4\u30d0\u30fc",
        "\u8fd1\u672a\u6765",
        "ai",
        "neon",
        "\u30cd\u30aa\u30f3",
        "\u90fd\u5e02",
        "city",
        "hologram",
        "\u30db\u30ed\u30b0\u30e9\u30e0",
        "android",
        "\u30a2\u30f3\u30c9\u30ed\u30a4\u30c9",
        "\u96fb\u8133",
    )
    return any(marker in world_text for marker in markers)


def build_world_visual_rule(context: dict) -> str:
    world_visual = collect_world_visual_context(context)
    if not world_visual:
        return ""
    rule = (
        "世界観ビジュアルの継続性:\n"
        f"{world_visual}\n"
        "世界観設定を、環境、小道具、照明、建築、素材、空気感に反映してください。"
        "指定された場所を、汎用的な部屋、無個性なスタジオ、普通の現代的な通りに置き換えないでください。"
    )
    if world_has_cyber_direction(context):
        rule += (
            "\nサイバー/近未来の強調: 場面に合う場合、背景を明確にサイバーパンクにしてください。重層的なネオン、"
            "ホログラム光、発光パネル、密度のある未来都市のディテール、ガラス/金属の表面、場面に自然なデータ表示風の空気感、"
            "高コントラストの映画的な夜の照明を入れてください。明示されない限り、ベージュ、汎用的な現代風、田舎風、無個性な背景は避けてください。"
        )
    return rule

def _lesson_board_requested(context: dict, state_json: dict | None = None) -> bool:
    state_json = state_json if isinstance(state_json, dict) else (context.get("state", {}).get("state_json") or {})
    room_snapshot = (context.get("session") or {}).get("room_snapshot_json") or {}
    room = context.get("room") or {}
    session_settings = (context.get("session") or {}).get("settings_json") or {}
    messages = context.get("messages") or []
    text_parts = [
        room_snapshot.get("title") if isinstance(room_snapshot, dict) else "",
        room_snapshot.get("conversation_objective") if isinstance(room_snapshot, dict) else "",
        room.get("title") if isinstance(room, dict) else "",
        room.get("conversation_objective") if isinstance(room, dict) else "",
        session_settings.get("conversation_objective") if isinstance(session_settings, dict) else "",
        state_json.get("location") if isinstance(state_json, dict) else "",
        state_json.get("background") if isinstance(state_json, dict) else "",
        (state_json.get("line_visual_note") or {}).get("background") if isinstance(state_json.get("line_visual_note"), dict) else "",
        (state_json.get("scene_progression") or {}).get("background") if isinstance(state_json.get("scene_progression"), dict) else "",
    ]
    for message in messages[-8:]:
        text_parts.append(message.get("message_text") or "")
    joined = "\n".join(str(part or "") for part in text_parts)
    markers = ("黒板", "板書", "教室", "授業", "講義", "講座", "先生", "歴史教室", "英語教室", "要点", "chalkboard", "blackboard")
    return any(marker in joined for marker in markers)


def build_lesson_board_rule(context: dict, state_json: dict | None = None) -> str:
    if not _lesson_board_requested(context, state_json):
        return ""
    recent_topic = ""
    for message in reversed(context.get("messages") or []):
        text = str(message.get("message_text") or "").strip()
        if text:
            recent_topic = text[:180]
            break
    return (
        "講義・教室シーンの板書ルール:\n"
        "現在の会話が授業、講義、教室、黒板、板書、要点確認に関係する場合、黒板を背景の飾りにせず、画面内の重要な被写体として大きく入れてください。"
        "キャラクターの横または背後に、読みやすい黒板を配置し、現在の話題に直接関係する短い要点を3〜5個だけ板書してください。"
        "年号、人物名、短いキーワード、矢印、簡単な図解は使ってよいです。長文は避け、文字は大きく読みやすくしてください。"
        "板書はキャラクターのセリフではなく、授業用の資料です。吹き出し、字幕、UIオーバーレイにはしないでください。"
        f"直近の板書テーマの手がかり: {recent_topic}"
    )


def apply_visual_style(prompt: str, context: dict) -> str:
    value = str(prompt or "").strip()
    state_json = (context.get("state") or {}).get("state_json") or {}
    style = collect_visual_style(context)
    world_rule = build_world_visual_rule(context)
    lesson_board_rule = build_lesson_board_rule(context, state_json)
    reference_rule = (
        "参照画像がある場合は、キャラクターデザインと画風の一貫性を保ってください。"
        "線の太さ、色使い、質感、顔の描き方、髪の描き方、ポーズの読みやすさ、キャラクターデザインの正確さを維持してください。"
        "明示されない限り、2D、3D、写実、絵画調などのスタイルを途中で切り替えないでください。"
        "新しい場面、服、背景でも、同じビジュアルシリーズに見えるようにしてください。"
    )
    blocks = [value]
    if world_rule:
        blocks.append(world_rule)
    if lesson_board_rule:
        blocks.append(lesson_board_rule)
    if style:
        blocks.append(f"画風指示: {style}")
    blocks.append(reference_rule)
    return "\n\n".join(block for block in blocks if block)

def forbid_text_in_image(prompt: str) -> str:
    value = str(prompt or "").strip()
    rule = (
        "セリフ吹き出し、漫画風の吹き出し、字幕、UIオーバーレイ、ロゴ、透かしは描かない。"
        "会話文は画像外のテキストボックスで表示するため、キャラクターの発話を画像内テキストにしない。"
        "ただし、黒板の板書、ノート、教科書、看板、端末画面、資料スライドなど、場面内に自然に存在する文字は必要最小限なら描いてよい。"
        "no speech bubbles, no dialogue text, no subtitles, no UI overlay, no watermark, no logo."
    )
    lowered = value.lower()
    if "no speech bubbles" in lowered and "セリフ吹き出し" in value:
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
    world_visual = collect_world_visual_context(context)

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
        f"世界観の視覚設定: {world_visual}",
        f"現在地のヒント: {line_visual_note.get('location') or scene_progression.get('location') or state_json.get('location') or ''}",
        f"背景のヒント: {line_visual_note.get('background') or scene_progression.get('background') or state_json.get('background') or ''}",
        f"場面要約: {line_visual_note.get('scene_moment') or scene_progression.get('focus_summary') or state_json.get('focus_summary') or ''}",
        f"感情トーン: {conversation_director.get('emotional_tone') or state_json.get('mood') or ''}",
        f"画風・スタイル指定: {visual_style}",
        "登場キャラクター:",
    ]
    learning_state = state_json.get("learning_director") or {}
    if context.get("live_chat_genre") == "learning" or learning_state:
        board_items = learning_state.get("board_items") or []
        aid_type = str(learning_state.get("teaching_aid_type") or "").strip().lower()
        aid_prompt = str(learning_state.get("teaching_aid_prompt") or "").strip()
        room = context.get("room") or {}
        teacher_name = room.get("teacher_character_name") or room.get("character_name") or ((active[0] or {}).get("name") if active else "")
        student_name = room.get("student_character_name") or ((active[1] or {}).get("name") if len(active) > 1 else "")
        lines.extend(
            [
                "",
                "学習モード画像要件:",
                "- 黒板、ホワイトボード、地図、年表、教材、図解、実験イメージのいずれかを画面内の主役にしてください。",
                "- map/timeline/diagram/experiment の教材ではキャラクターを無理に入れず、教材の読みやすさを最優先してください。",
                "- board の教材ではキャラクターを先生役として、板書や図解の横に配置して構いません。",
                "- 吹き出し、字幕、UIオーバーレイ、ロゴ、透かしは禁止です。",
                "- 黒板、ノート、教材、図解、地図、年表、実験ラベルに自然に存在する文字は許可します。",
                "- 恋愛イベントCG、施設デート、身体的ハプニングの演出に寄せないでください。",
            ]
        )
        if aid_type:
            lines.append(f"教材タイプ: {aid_type}")
        if aid_prompt:
            lines.append(f"教材画像の目的: {aid_prompt}")
        if board_items:
            lines.extend(["黒板に入れたい要点:", *[f"- {item}" for item in board_items[:8]]])
        if teacher_name or student_name:
            lines.extend(
                [
                    f"先生役: {teacher_name}",
                    f"生徒役: {student_name or '未設定'}",
                    "プレイヤーは生徒役として発言します。生徒役が設定されている場合、板書・教室シーンでは先生と生徒を一緒に配置してください。",
                    "先生は説明し、生徒は聞く、質問する、驚く、ノートを取るなど学習者として反応します。無関係な人物は追加しないでください。",
                ]
            )
    world_map_context = (context.get("world_map") or {}).get("prompt_context")
    if world_map_context:
        lines.extend(["ワールドマップ登録施設:", world_map_context])
    if world_has_cyber_direction(context):
        lines.extend(
            [
                "サイバーパンク視覚要件:",
                "- 場面に合う場合、背景を明確にサイバーパンクにしてください。ネオン、ホログラム光、発光パネル、ガラス/金属、密度のある近未来都市ディテールを入れてください。",
                "- セリフ吹き出し、字幕、UIオーバーレイ、ロゴ、透かしは描かないでください。黒板、資料、端末、看板など場面内に自然な文字は必要最小限なら使って構いません。",
                "- 明示されない限り、汎用的な部屋、普通の現代的な通り、ベージュの室内、田舎風景、無個性なスタジオ背景は避けてください。",
            ]
        )
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
    world_rule = build_world_visual_rule(context)

    prompt_parts = [
        "この会話に合う、ドラマチックなノベルゲーム風イベントCGを生成してください。",
        "視点はプレイヤーの一人称視点です。プレイヤー自身は画像に描かないでください。",
        f"登場キャラクターは{character_names}です。",
        f"今この瞬間は「{scene_summary}」です。",
        f"雰囲気は{mood}です。",
        f"構図は{camera}にしてください。",
    ]
    learning_state = state_json.get("learning_director") or {}
    if context.get("live_chat_genre") == "learning" or learning_state:
        board_items = learning_state.get("board_items") or []
        aid_type = str(learning_state.get("teaching_aid_type") or "").strip().lower()
        aid_prompt = str(learning_state.get("teaching_aid_prompt") or "").strip()
        room = context.get("room") or {}
        teacher_name = room.get("teacher_character_name") or room.get("character_name") or (active[0].get("name") if active else "")
        student_name = room.get("student_character_name") or (active[1].get("name") if len(active) > 1 else "")
        prompt_parts = [
            "学習モードの授業画像を生成してください。",
            "黒板、ホワイトボード、地図、年表、教材、図解、実験イメージ、写真資料のいずれかを画面内の主役にしてください。",
            "吹き出し、字幕、UIオーバーレイ、ロゴ、透かしは禁止です。",
            "黒板、ノート、教材、図解、地図、年表、実験ラベルに自然に存在する文字は許可します。",
            f"授業の瞬間は「{scene_summary}」です。",
        ]
        if aid_type in {"map", "timeline", "diagram", "experiment", "photo"}:
            prompt_parts.append("キャラクター写真ではなく、読みやすい学習教材画像として作ってください。")
        else:
            prompt_parts.append(f"登場キャラクターは{character_names}です。先生役として板書や図解の横に配置してください。")
        if aid_type:
            prompt_parts.append(f"教材タイプ: {aid_type}")
        if aid_prompt:
            prompt_parts.append(f"教材画像の目的: {aid_prompt}")
        if board_items:
            prompt_parts.append("黒板に入れたい要点: " + "、".join(str(item) for item in board_items[:8]))
        if teacher_name or student_name:
            prompt_parts.append(f"先生役は{teacher_name}、生徒役は{student_name or '未設定'}です。")
            prompt_parts.append("プレイヤーは生徒役として発言します。生徒役が設定されている場合、板書・教室シーンでは先生と生徒を一緒に配置してください。")
    if location:
        prompt_parts.append(f"会話内容に合う背景として「{location}」が自然に分かるように描いてください。")
    if world_rule:
        prompt_parts.append(f"背景に反映する世界観の視覚設定: {world_rule}")
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
        value = f"一人称視点、見る人がプレイヤー本人、プレイヤーキャラクターは描かない、{value}"

    pov_requirements = (
        "一人称視点",
        "見る人がプレイヤー本人",
        "プレイヤーキャラクターは描かない",
    )
    lowered = value.lower()
    missing = [item for item in pov_requirements if item not in lowered]
    if missing:
        if any("\u3040" <= ch <= "\u30ff" or "\u4e00" <= ch <= "\u9fff" for ch in value):
            prefix = "プレイヤーの一人称視点、プレイヤー自身は画像に描かない"
        else:
            prefix = "一人称視点、見る人がプレイヤー本人、プレイヤーキャラクターは描かない"
        value = f"{prefix}, {value}"
    return value
