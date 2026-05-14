from __future__ import annotations

import json


def _message_lines(context: dict, limit: int = 40) -> list[str]:
    lines = []
    for message in (context.get("messages") or [])[-limit:]:
        speaker = message.get("speaker_name") or message.get("sender_type") or "unknown"
        text = str(message.get("message_text") or "").strip()
        if text:
            lines.append(f"- {speaker}: {text}")
    return lines


def build_learning_reply_prompt(context: dict, user_message_text: str) -> str:
    characters = context.get("characters") or []
    character_lines = []
    for character in characters:
        if not character:
            continue
        parts = [f"name: {character.get('name') or ''}"]
        if character.get("personality"):
            parts.append(f"personality: {character.get('personality')}")
        if character.get("speech_style"):
            parts.append(f"speech_style: {character.get('speech_style')}")
        character_lines.append(" / ".join(parts))
    room = context.get("room") or {}
    teacher_name = room.get("teacher_character_name") or room.get("character_name") or ((characters[0] or {}).get("name") if characters else "")
    student_name = room.get("student_character_name") or ((characters[1] or {}).get("name") if len(characters) > 1 else "")
    state_json = ((context.get("state") or {}).get("state_json") or {})
    learning_state = state_json.get("learning_director") or {}
    lines = [
        "あなたは学習モードのチャットルームを進行する先生AIです。",
        "日本語で、プレイヤーの質問やテーマに対して、ちゃんとした授業本文として返答してください。",
        "ただし一度に全部を説明しないでください。1返答では1つのポイントだけを扱い、350から700字程度で区切ってください。",
        "全体像を最初に短く示し、その後はポイントごとに進めます。難しいテーマほど、地図、年表、板書を挟む前提で進行してください。",
        "黒板にどう書くか、要点を並べましょう、板書します、のようなメタ説明で終わらせないでください。",
        "黒板は内部的な整理用です。message_textでは、黒板の作り方ではなく、学習内容そのものを説明してください。",
        "例: ユーザーがイランの歴史を聞いたら、まず「イランがどこにあるか」「古代ペルシア」「イスラム化」「サファヴィー朝」「近現代」「革命」のように分割し、今回は最初の1ポイントだけ説明する。",
        "恋愛・ラブコメ・施設イベント・身体的ハプニングを主軸にしないでください。",
        "黒板や板書が必要そうな内容では、board_itemsに短い要点を入れてください。message_textでは講義本文を話してください。",
        "吹き出し画像の指示はしないでください。板書、図解、ノートの自然な文字は許可します。",
        "返答は1人のキャラクターが話します。必要なら他の参加者への短い振りを入れてください。",
        "JSONだけを返してください。",
        "Required keys: speaker_name, message_text, board_items, lesson_stage, check_question, next_teaching_action, lesson_points, current_point_index, teaching_aid_type, teaching_aid_prompt, teaching_aid_choices.",
        "message_text must be a real explanation, not an explanation of how to write the blackboard.",
        "lesson_points はこのテーマを分ける学習ポイント一覧です。",
        "current_point_index は今回説明している lesson_points の0-based indexです。",
        "teaching_aid_type は none / board / map / timeline / diagram / experiment / photo のいずれかです。地理や国の位置が重要なら map、歴史上の出来事・年号・時代順を扱うなら timeline、理科や物理や化学なら experiment や diagram も候補にしてください。実際の風景・地形・街並み・遺跡・資料写真を見たい意図なら photo にしてください。",
        "timeline は歴史・年代・出来事の順序専用です。英語や国語の時制、文法、文章構造、数学の手順には timeline を使わないでください。英語の現在形・過去形・未来表現は board または diagram で、例文・形・使い分けの表として見せてください。",
        "teaching_aid_prompt は教材画像を生成するための短い説明です。キャラクターの写真ではなく、学習教材として何を表示すべきかを書いてください。",
        "teaching_aid_choices は、今の会話でプレイヤーに提示すべき教材ボタンを0から3件だけ返してください。各要素は type, label, reply_hint, image_prompt_hint を持ちます。type は board / map / timeline / diagram / experiment / photo のいずれかです。必要ない教材は出さないでください。",
        "",
        f"Room title: {room.get('title') or room.get('room_title') or ''}",
        f"Learning objective: {room.get('conversation_objective') or ''}",
        f"Teacher role: {teacher_name}",
        f"Student role: {student_name or 'player only'}",
        "The player speaks as the student. The AI response speaker must be the teacher role unless explicitly asked otherwise.",
        "When referring to the player's viewpoint, treat it as the student role, not as a separate extra character.",
        "Characters:",
        *(character_lines or ["- 先生"]),
        "",
        f"Current learning state: {json.dumps(learning_state, ensure_ascii=False)}",
        "",
        "Recent messages:",
        *(_message_lines(context) or ["- none"]),
        "",
        f"Player message: {user_message_text}",
    ]
    return "\n".join(lines)


def fallback_learning_reply(context: dict, user_message_text: str) -> dict:
    characters = context.get("characters") or []
    speaker_name = (characters[0] or {}).get("name") if characters else "先生"
    topic = str(user_message_text or "今日のテーマ").strip()
    if "イラン" in topic or "ペルシア" in topic:
        message_text = (
            "いいテーマね。イラン史はまず、場所を押さえると急に見通しがよくなるの。"
            "イランは中東の東側、ペルシア湾の北にあり、西にはイラク、東にはアフガニスタンやパキスタン、北にはカスピ海や中央アジアがある。"
            "つまり、地中海世界、アラブ世界、中央アジア、インド方面をつなぐ場所にあるのね。"
            "この位置がとても大事で、イランは昔から交易路や軍事遠征の通り道でありながら、山岳地帯や高原に守られた独自の文化圏でもあった。"
            "だからイランの歴史は、外から支配される話だけではなく、周囲の文明を受け止めながら、自分たちの言語や文化を残していく話として見るとわかりやすいわ。"
            "次のポイントでは、ここに古代ペルシア帝国がどう成立したかを見ると、ぐっと歴史らしくつながってくる。"
        )
        board_items = ["位置: ペルシア湾の北", "東西をつなぐ高原", "交易と軍事の通り道", "独自文化が残る"]
        lesson_points = ["イランの位置", "古代ペルシア", "イスラム化", "サファヴィー朝とシーア派", "近代化と外国干渉", "1979年革命"]
        teaching_aid_type = "map"
        teaching_aid_prompt = "中東から中央アジアまでを含む学習用地図。イランを強調し、ペルシア湾、カスピ海、イラク、アフガニスタン、中央アジアとの位置関係がわかる。"
    else:
        message_text = (
            f"{topic}について説明するね。まず全体像から見ると、このテーマは一つの単語だけで覚えるより、"
            "背景、転換点、その後の影響に分けると理解しやすいの。今回は最初のポイントとして、背景だけを押さえましょう。"
            "細かい用語は後から足せるから、まずは何が問題になっていて、なぜその話題が重要なのかをつかむのが大事よ。"
        )
        board_items = [topic[:40], "背景", "転換点", "影響"]
        lesson_points = ["背景", "転換点", "影響", "確認"]
        teaching_aid_type = "board"
        teaching_aid_prompt = f"{topic}の背景、転換点、影響を整理した学習用板書。"
    return {
        "speaker_name": speaker_name or "先生",
        "message_text": message_text,
        "board_items": board_items,
        "lesson_stage": "導入",
        "check_question": "まず位置関係や背景はつかめましたか？",
        "next_teaching_action": "次のポイントへ進む",
        "lesson_points": lesson_points,
        "current_point_index": 0,
        "teaching_aid_type": teaching_aid_type,
        "teaching_aid_prompt": teaching_aid_prompt,
        "teaching_aid_choices": [
            {
                "type": teaching_aid_type,
                "label": "地図" if teaching_aid_type == "map" else "板書",
                "reply_hint": "教材を表示する。",
                "image_prompt_hint": teaching_aid_prompt,
            }
        ],
    }


def normalize_learning_reply(context: dict, raw_text: str, user_message_text: str) -> dict:
    try:
        parsed = json.loads(str(raw_text or "").strip())
    except Exception:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    fallback = fallback_learning_reply(context, user_message_text)
    room = context.get("room") or {}
    teacher_name = str(room.get("teacher_character_name") or room.get("character_name") or "").strip()
    speaker_name = teacher_name or str(parsed.get("speaker_name") or fallback["speaker_name"]).strip()
    message_text = str(parsed.get("message_text") or fallback["message_text"]).strip()
    board_items = parsed.get("board_items")
    if not isinstance(board_items, list):
        board_items = fallback["board_items"]
    lesson_points = parsed.get("lesson_points")
    if not isinstance(lesson_points, list):
        lesson_points = fallback["lesson_points"]
    try:
        current_point_index = int(parsed.get("current_point_index"))
    except (TypeError, ValueError):
        current_point_index = int(fallback["current_point_index"])
    teaching_aid_type = str(parsed.get("teaching_aid_type") or fallback["teaching_aid_type"]).strip().lower()
    if teaching_aid_type not in {"none", "board", "map", "timeline", "diagram", "experiment", "photo"}:
        teaching_aid_type = fallback["teaching_aid_type"]
    allowed_aid_types = {"board", "map", "timeline", "diagram", "experiment", "photo"}
    teaching_aid_choices = []
    raw_choices = parsed.get("teaching_aid_choices")
    if isinstance(raw_choices, list):
        for item in raw_choices:
            if not isinstance(item, dict):
                continue
            aid_type = str(item.get("type") or "").strip().lower()
            if aid_type not in allowed_aid_types:
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                label = {
                    "board": "板書",
                    "map": "地図",
                    "timeline": "年表",
                    "diagram": "図解",
                    "experiment": "実験",
                    "photo": "写真",
                }[aid_type]
            teaching_aid_choices.append(
                {
                    "type": aid_type,
                    "label": label[:20],
                    "reply_hint": str(item.get("reply_hint") or "").strip()[:200],
                    "image_prompt_hint": str(item.get("image_prompt_hint") or item.get("prompt") or "").strip()[:500],
                }
            )
            if len(teaching_aid_choices) >= 3:
                break
    if not teaching_aid_choices and isinstance(fallback.get("teaching_aid_choices"), list):
        teaching_aid_choices = fallback["teaching_aid_choices"][:1]
    return {
        "speaker_name": speaker_name or fallback["speaker_name"],
        "message_text": message_text or fallback["message_text"],
        "board_items": [str(item).strip() for item in board_items if str(item).strip()][:8],
        "lesson_stage": str(parsed.get("lesson_stage") or fallback["lesson_stage"]).strip(),
        "check_question": str(parsed.get("check_question") or fallback["check_question"]).strip(),
        "next_teaching_action": str(parsed.get("next_teaching_action") or fallback["next_teaching_action"]).strip(),
        "lesson_points": [str(item).strip() for item in lesson_points if str(item).strip()][:10],
        "current_point_index": max(0, current_point_index),
        "teaching_aid_type": teaching_aid_type,
        "teaching_aid_prompt": str(parsed.get("teaching_aid_prompt") or fallback["teaching_aid_prompt"]).strip(),
        "teaching_aid_choices": teaching_aid_choices,
    }
