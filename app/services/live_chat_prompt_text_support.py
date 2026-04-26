from __future__ import annotations

from datetime import datetime


MEMORY_CATEGORIES = ("likes", "dislikes", "hobbies", "taboos", "memorable_events")
ROMANCE_KEYS = ("favorite_approach", "avoid_approach", "attraction_points", "boundaries")


def get_session_objective(context: dict) -> str | None:
    room_snapshot = context.get("session", {}).get("room_snapshot_json") or {}
    if isinstance(room_snapshot, dict):
        value = str(room_snapshot.get("conversation_objective") or "").strip()
        if value:
            return value
    room = context.get("room") or {}
    if isinstance(room, dict):
        value = str(room.get("conversation_objective") or "").strip()
        if value:
            return value
    session_settings = context.get("session", {}).get("settings_json") or {}
    if isinstance(session_settings, dict):
        value = str(
            session_settings.get("conversation_objective")
            or session_settings.get("session_objective")
            or ""
        ).strip()
        return value or None
    return None


def _conversation_score(evaluation: dict | None) -> int | None:
    if not isinstance(evaluation, dict):
        return None
    try:
        return int(evaluation.get("score"))
    except (TypeError, ValueError):
        return None


def _is_romance_goal(session_objective: str | None, evaluation: dict | None = None) -> bool:
    objective = str(session_objective or "")
    theme = str((evaluation or {}).get("theme") or "")
    return theme == "romance" or any(token in objective for token in ("恋愛", "好き", "惚れ", "感情"))


def _normalize_memory_items(values) -> list[str]:
    normalized = []
    seen = set()
    for value in values or []:
        text = str(value or "").strip().strip("。,. ")
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text[:160])
    return normalized


def _normalize_memory_profile(profile: dict | None) -> dict:
    profile = dict(profile or {})
    romance = dict(profile.get("romance_preferences") or {})
    normalized = {key: _normalize_memory_items(profile.get(key) or []) for key in MEMORY_CATEGORIES}
    normalized["romance_preferences"] = {
        key: _normalize_memory_items(romance.get(key) or [])
        for key in ROMANCE_KEYS
    }
    return normalized


def _character_profile(character: dict) -> dict:
    profile = _normalize_memory_profile(character.get("memory_profile") or {})
    if not profile["likes"] and character.get("favorite_items"):
        profile["likes"] = _normalize_memory_items(character.get("favorite_items") or [])
    return profile


def _merge_lists(*sources) -> list[str]:
    merged = []
    seen = set()
    for source in sources:
        for item in source or []:
            text = str(item or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(text[:160])
    return merged


def _text_to_candidates(text: str) -> list[str]:
    normalized = str(text or "").replace("、", ",").replace("。", ",").replace("・", ",").replace("/", ",")
    return _normalize_memory_items(part for part in normalized.split(","))


def _extract_by_phrase(text: str, triggers: tuple[str, ...]) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    candidates = []
    for trigger in triggers:
        if trigger not in text:
            continue
        head, tail = text.split(trigger, 1)
        for chunk in (head, tail):
            candidates.extend(_text_to_candidates(chunk[-40:] if chunk is head else chunk[:40]))
    return [item for item in candidates if 1 <= len(item) <= 40]


def _extract_likes(text: str) -> list[str]:
    text = str(text or "")
    if not any(token in text for token in ("好き", "お気に入り", "好物", "欲しい", "ほしい")):
        return []
    return _extract_by_phrase(text, ("好き", "お気に入り", "好物", "欲しい", "ほしい"))


def _extract_dislikes(text: str) -> list[str]:
    text = str(text or "")
    if not any(token in text for token in ("嫌い", "苦手", "嫌だ", "勘弁")):
        return []
    return _extract_by_phrase(text, ("嫌い", "苦手", "嫌だ", "勘弁"))


def _extract_hobbies(text: str) -> list[str]:
    text = str(text or "")
    if not any(token in text for token in ("趣味", "好きなこと", "よくする", "よくやる")):
        return []
    return _extract_by_phrase(text, ("趣味", "好きなこと", "よくする", "よくやる"))


def _extract_taboos(text: str) -> list[str]:
    text = str(text or "")
    if not any(token in text for token in ("触れられたくない", "聞かれたくない", "やめて", "言わないで", "詮索")):
        return []
    return _extract_by_phrase(text, ("触れられたくない", "聞かれたくない", "やめて", "言わないで", "詮索"))


def _extract_romance_preferences(text: str) -> dict:
    text = str(text or "")
    favorite_approach = []
    avoid_approach = []
    attraction_points = []
    boundaries = []
    if any(token in text for token in ("優しく", "自然に", "丁寧に", "寄り添")) and any(token in text for token in ("されると嬉しい", "されるのが好き", "弱い")):
        favorite_approach.extend(_text_to_candidates(text))
    if any(token in text for token in ("命令口調", "馴れ馴れし", "下品", "強引")):
        avoid_approach.extend(_text_to_candidates(text))
    if any(token in text for token in ("惹かれる", "好きになる", "弱い", "ときめく")):
        attraction_points.extend(_text_to_candidates(text))
    if any(token in text for token in ("初対面で", "いきなり", "やめてほしい", "苦手")):
        boundaries.extend(_text_to_candidates(text))
    return {
        "favorite_approach": _normalize_memory_items(favorite_approach),
        "avoid_approach": _normalize_memory_items(avoid_approach),
        "attraction_points": _normalize_memory_items(attraction_points),
        "boundaries": _normalize_memory_items(boundaries),
    }


def _extract_character_memory_note(text: str) -> str | None:
    stripped = str(text or "").strip()
    if not stripped:
        return None
    markers = (
        "好き", "嫌い", "苦手", "趣味", "お気に入り", "欲しい", "ほしい",
        "触れられたくない", "聞かれたくない", "優しく", "命令口調",
    )
    if any(marker in stripped for marker in markers):
        return stripped[:160]
    return None


def _build_character_memory_summary(character_memory: dict | None) -> str | None:
    memory = _normalize_memory_profile(character_memory or {})
    romance = memory.get("romance_preferences") or {}
    parts = []
    for key in ("likes", "dislikes", "hobbies", "taboos", "memorable_events"):
        values = memory.get(key) or []
        if values:
            parts.append(f"{key}={', '.join(values[:4])}")
    for key in ROMANCE_KEYS:
        values = romance.get(key) or []
        if values:
            parts.append(f"romance.{key}={', '.join(values[:3])}")
    return " / ".join(parts) if parts else None


def _flatten_character_memory(character: dict, session_memory_map: dict | None = None) -> dict:
    profile = _character_profile(character)
    session_memory_map = session_memory_map or {}
    session_memory = _normalize_memory_profile(session_memory_map.get(character.get("name")) or {})
    merged = {key: _merge_lists(profile.get(key) or [], session_memory.get(key) or []) for key in MEMORY_CATEGORIES}
    merged["romance_preferences"] = {
        key: _merge_lists(
            (profile.get("romance_preferences") or {}).get(key) or [],
            (session_memory.get("romance_preferences") or {}).get(key) or [],
        )
        for key in ROMANCE_KEYS
    }
    return merged


def _analyze_player_memory_match(context: dict) -> dict:
    last_user_message = next(
        (item for item in reversed(context.get("messages") or []) if item.get("sender_type") == "user"),
        None,
    )
    if not last_user_message:
        return {"bonus": 0, "penalty": 0, "reasons": []}
    text = str(last_user_message.get("message_text") or "")
    if not text:
        return {"bonus": 0, "penalty": 0, "reasons": []}
    session_memory_map = ((context.get("state") or {}).get("state_json") or {}).get("session_memory", {}).get("character_memories") or {}
    bonus = 0
    penalty = 0
    reasons = []
    for character in context.get("characters") or []:
        memory = _flatten_character_memory(character, session_memory_map)
        name = character.get("name") or "character"
        for item in memory.get("likes") or []:
            if item and item in text:
                bonus += 4
                reasons.append(f"{name} likes {item}")
        for item in memory.get("hobbies") or []:
            if item and item in text:
                bonus += 6
                reasons.append(f"{name} is interested in hobby {item}")
        for item in memory.get("dislikes") or []:
            if item and item in text:
                penalty += 5
                reasons.append(f"{name} dislikes {item}")
        for item in memory.get("taboos") or []:
            if item and item in text:
                penalty += 10
                reasons.append(f"{name} has taboo topic {item}")
        romance = memory.get("romance_preferences") or {}
        for item in romance.get("favorite_approach") or []:
            if item and item in text:
                bonus += 8
                reasons.append(f"{name} responds well to {item}")
        for item in romance.get("attraction_points") or []:
            if item and item in text:
                bonus += 8
                reasons.append(f"{name} is attracted by {item}")
        for item in romance.get("avoid_approach") or []:
            if item and item in text:
                penalty += 10
                reasons.append(f"{name} dislikes approach {item}")
        for item in romance.get("boundaries") or []:
            if item and item in text:
                penalty += 15
                reasons.append(f"{name} feels boundary crossed by {item}")
    return {"bonus": bonus, "penalty": penalty, "reasons": reasons}


def build_opening_prompt(context: dict) -> str:
    session_objective = get_session_objective(context)
    state_json = (context.get("state") or {}).get("state_json") or {}
    relationship_state = state_json.get("relationship_state") or {}
    lines = [
        "You are the opening line generator for a live chat visual novel.",
        "Return only a JSON object.",
        "Required keys: speaker_name, message_text.",
        "speaker_name must be one of the existing characters.",
        "message_text must be one natural opening line, not narration.",
        "Avoid generic guide-like phrasing or exposition dumping.",
        "Make the opening feel like this character is choosing to talk first.",
        f"Project: {context['project'].get('title') or 'Untitled'}",
        f"Player name: {context['session'].get('player_name') or 'Player'}",
    ]
    if session_objective:
        lines.append(f"Session objective: {session_objective}")
    if context["world"].get("overview"):
        lines.append(f"World overview: {context['world']['overview']}")
    if relationship_state:
        lines.append("Relationship state:")
        for name, metrics in relationship_state.items():
            if isinstance(metrics, dict):
                metric_text = ", ".join(
                    f"{key}={metrics.get(key)}"
                    for key in ("affection", "interest", "trust", "tension")
                    if metrics.get(key) is not None
                )
                if metric_text:
                    lines.append(f"- {name}: {metric_text}")
    lines.append("Characters:")
    for character in context["characters"]:
        lines.append(
            f"- {character['name']}: nickname={character.get('nickname') or ''}, gender={character.get('gender') or ''}, first_person={character.get('first_person') or ''}, second_person={character.get('second_person') or ''}, personality={character.get('personality') or ''}, speech_style={character.get('speech_style') or ''}, speech_sample={character.get('speech_sample') or ''}, ng_rules={character.get('ng_rules') or ''}"
        )
        if character.get("nickname"):
            lines.append(
                f"  The character may naturally tell the player how to call them, using nickname={character.get('nickname')} as conversational material."
            )
        summary = _build_character_memory_summary(_character_profile(character))
        if summary:
            lines.append(f"  memory={summary}")
    return "\n".join(lines)


def fallback_opening_message(context: dict) -> dict:
    speaker = context["characters"][0]["name"] if context["characters"] else "Character"
    player_name = context["session"].get("player_name") or "あなた"
    speech_style = context["characters"][0].get("speech_style") if context["characters"] else ""
    personality = context["characters"][0].get("personality") if context["characters"] else ""
    if any(token in str(speech_style) for token in ("カジュアル", "砕け", "フランク")) or any(token in str(personality) for token in ("明る", "気さく", "フランク")):
        text = f"{player_name}、来たんだ。今日はどんな話をしたい？"
    elif any(token in str(speech_style) for token in ("丁寧", "上品")) or any(token in str(personality) for token in ("穏やか", "落ち着", "知的")):
        text = f"{player_name}さん、こんにちは。今日はどんなお話をしましょうか。"
    else:
        text = f"{player_name}、こんにちは。少し話してみようか。"
    return {"speaker_name": speaker, "message_text": text}


def normalize_compare_text(text: str) -> str:
    value = str(text or "").strip()
    for token in ("…", "...", "・・", "・", " ", "\n", "\r", "　"):
        value = value.replace(token, "")
    return value


def is_affirmative_progress_message(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    positive_keywords = (
        "はい", "いいよ", "いいです", "分かった", "わかった", "進もう",
        "連れて行って", "見せて", "教えて", "ok", "okay", "sure", "yes",
    )
    return any(keyword in lowered for keyword in positive_keywords)


def recent_transition_offer_exists(context: dict) -> bool:
    transition_keywords = ("行こう", "見てみよう", "連れて", "次は", "向かおう", "進もう")
    for message in reversed(context["messages"][-4:]):
        if message.get("sender_type") != "character":
            continue
        text = str(message.get("message_text") or "")
        if any(keyword in text for keyword in transition_keywords):
            return True
    return False


def is_generic_transition_reply(text: str) -> bool:
    normalized = normalize_compare_text(text)
    generic_keywords = ("行こう", "見てみよう", "連れていく", "大丈夫")
    return len(normalized) <= 32 and any(keyword in text for keyword in generic_keywords)


def build_reply_prompt(context: dict, user_message_text: str) -> str:
    session_objective = get_session_objective(context)
    state_json = context["state"].get("state_json") or {}
    session_memory = state_json.get("session_memory") or {}
    scene_progression = state_json.get("scene_progression") or {}
    conversation_director = state_json.get("conversation_director") or {}
    relationship_state = state_json.get("relationship_state") or {}
    visual_state = state_json.get("visual_state") or {}
    displayed_image = state_json.get("displayed_image_observation") or {}
    conversation_evaluation = state_json.get("conversation_evaluation") or {}
    lines = [
        "You are the reply generator for a live visual novel conversation.",
        "Return only a JSON object.",
        "Required keys: speaker_name, message_text.",
        "speaker_name must be one of the active characters.",
        "message_text must be a single natural spoken line, not narration.",
        "Keep the reply proactive, emotionally colored, and character-specific.",
        "Do not answer like a generic guide unless the character truly would.",
        f"Player name: {context['session'].get('player_name') or '主人公'}",
    ]
    if session_objective:
        lines.append(f"Session objective: {session_objective}")
    if context["world"].get("overview"):
        lines.append(f"World overview: {context['world']['overview']}")
    if scene_progression:
        lines.append(f"Current scene phase: {scene_progression.get('scene_phase') or ''}")
        lines.append(f"Current location: {scene_progression.get('location') or ''}")
        lines.append(f"Scene focus: {scene_progression.get('focus_summary') or ''}")
        lines.append(f"Next topic: {scene_progression.get('next_topic') or ''}")
    if conversation_director:
        lines.append(f"Turn intent: {conversation_director.get('turn_intent') or ''}")
        lines.append(f"Emotional tone: {conversation_director.get('emotional_tone') or ''}")
        lines.append(f"Relationship goal: {conversation_director.get('relationship_goal') or ''}")
        lines.append(f"Scene goal: {conversation_director.get('scene_goal') or ''}")
    if visual_state:
        lines.append(f"Current visual location: {visual_state.get('location') or ''}")
        lines.append(f"Current visual background: {visual_state.get('background_details') or ''}")
    if displayed_image:
        lines.append("Actual displayed image observation:")
        lines.append(f"- location: {displayed_image.get('location') or ''}")
        lines.append(f"- background: {displayed_image.get('background') or ''}")
        lines.append(f"- visible characters: {displayed_image.get('visible_characters') or []}")
        lines.append(f"- poses: {displayed_image.get('character_poses') or ''}")
        lines.append(f"- expressions: {displayed_image.get('character_expressions') or ''}")
        lines.append(f"- mood: {displayed_image.get('mood') or ''}")
        lines.append(f"- notable objects: {displayed_image.get('notable_objects') or []}")
        lines.append(f"- summary: {displayed_image.get('short_summary') or ''}")
        lines.append(
            "Use the actual displayed image observation as the highest priority for where the characters are and what they can refer to."
        )
    if conversation_evaluation:
        lines.append(f"Conversation progress score: {conversation_evaluation.get('score')}")
        lines.append(f"Conversation progress reason: {conversation_evaluation.get('reason') or ''}")
        score = _conversation_score(conversation_evaluation)
        is_romance = _is_romance_goal(session_objective, conversation_evaluation)
        if score is not None and score <= 35:
            lines.append(
                "Low progress recovery rule: the character must not stay passive. "
                "They should create one easy emotional opening that moves toward the session objective."
            )
            if is_romance:
                lines.append(
                    "For a low romance score, use a small personal disclosure, gentle affection, teasing warmth, "
                    "or a character-specific invitation that makes the player want to get closer."
                )
            else:
                lines.append(
                    "For a low general score, make the objective feel more attractive and offer one concrete hook the player can answer."
                )
        elif score is not None and score <= 65:
            lines.append(
                "Medium progress rule: keep momentum by rewarding useful player input and steering to the next attractive topic."
            )
        elif score is not None and score >= 80:
            lines.append(
                "High progress rule: deepen the exchange with a more intimate, confident, or goal-advancing response."
            )
    if relationship_state:
        lines.append("Relationship state:")
        for name, metrics in relationship_state.items():
            if isinstance(metrics, dict):
                lines.append(
                    f"- {name}: affection={metrics.get('affection', 0)}, interest={metrics.get('interest', 0)}, trust={metrics.get('trust', 0)}, tension={metrics.get('tension', 0)}"
                )
    if session_memory.get("player_preferences"):
        lines.append(f"Player preference memo: {session_memory['player_preferences']}")
    if session_memory.get("recent_topics"):
        lines.append(f"Recent topics: {session_memory['recent_topics']}")
    character_memories = session_memory.get("character_memories") or {}
    if character_memories:
        lines.append("Character memory:")
        for name, memory in character_memories.items():
            summary = _build_character_memory_summary(memory)
            if summary:
                lines.append(f"- {name}: {summary}")
    lines.append("Characters:")
    for character in context["characters"]:
        lines.append(
            f"- {character['name']}: nickname={character.get('nickname') or ''}, gender={character.get('gender') or ''}, first_person={character.get('first_person') or ''}, second_person={character.get('second_person') or ''}, personality={character.get('personality') or ''}, speech_style={character.get('speech_style') or ''}, speech_sample={character.get('speech_sample') or ''}, ng_rules={character.get('ng_rules') or ''}"
        )
        if character.get("nickname"):
            lines.append(
                f"  If the player asks how to call them, answer naturally based on nickname={character.get('nickname')}."
            )
        summary = _build_character_memory_summary(_flatten_character_memory(character, character_memories))
        if summary:
            lines.append(f"  memory={summary}")
    lines.append("If the player mentions something a character likes, remembers, or responds well to, let that improve the reaction.")
    lines.append("If the player touches a taboo, dislike, or romantic boundary, cool the reaction and let it affect the tone.")
    lines.append(
        "Avoid empty loops such as only saying 'what do you want to talk about' or simply agreeing; always add a new emotional or concrete hook."
    )
    lines.append("Recent conversation:")
    for message in context["messages"][-8:]:
        lines.append(f"- {message.get('speaker_name') or message.get('sender_type')}: {message.get('message_text')}")
    lines.append(f"- player: {user_message_text}")
    return "\n".join(lines)


def fallback_reply(context: dict, user_message_text: str) -> dict:
    speaker = context["characters"][0]["name"] if context["characters"] else "Character"
    shortened = user_message_text[:40]
    memory_match = _analyze_player_memory_match(context)
    state_json = context["state"].get("state_json") or {}
    conversation_evaluation = state_json.get("conversation_evaluation") or {}
    score = _conversation_score(conversation_evaluation)
    is_romance = _is_romance_goal(get_session_objective(context), conversation_evaluation)
    if memory_match["penalty"] > 0:
        message = f"{shortened}……その話は、あまり気分がよくないかも。"
    elif memory_match["bonus"] > 0:
        message = f"{shortened}……覚えていてくれたんだね。少し嬉しい。"
    elif score is not None and score <= 35 and is_romance:
        message = f"{shortened}……ねえ、少しだけあなたのことを知りたくなった。今の気持ち、わたしに聞かせて。"
    elif score is not None and score <= 35:
        message = f"{shortened}……それなら、わたしから一つ面白い話を出すね。ここから少し踏み込んでみよう。"
    else:
        message = f"{shortened}……うん、その話は気になる。もう少し聞かせて。"
    return {"speaker_name": speaker, "message_text": message}


def build_input_intent_prompt(context: dict, user_message_text: str) -> str:
    state_json = context["state"].get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    lines = [
        "You classify the latest input for a live visual novel chat.",
        "Return only a JSON object.",
        "Required keys: intent, reason, should_generate_image.",
        "intent must be one of: dialogue, narration, visual_request.",
        "dialogue: the player is speaking directly to the character.",
        "narration: the player is describing a scene transition, action, time skip, or staging direction, not asking for a spoken answer.",
        "visual_request: the player wants to see an image, outfit, location, object, or event CG.",
        "If the input is like 'そして僕たちは店の外に出た。', classify it as narration.",
        "If the input is like 'この服を着て外に出た場面を見せて', classify it as visual_request.",
        f"Current location: {state_json.get('location') or scene_progression.get('location') or ''}",
        f"Current scene: {scene_progression.get('focus_summary') or state_json.get('focus_summary') or ''}",
        "Recent conversation:",
    ]
    for message in context["messages"][-6:]:
        lines.append(f"- {message.get('speaker_name') or message.get('sender_type')}: {message.get('message_text')}")
    lines.append(f"Latest input: {user_message_text}")
    return "\n".join(lines)


def fallback_input_intent(user_message_text: str) -> dict:
    text = str(user_message_text or "").strip()
    lowered = text.lower()
    narration_markers = (
        "そして",
        "その後",
        "しばらくして",
        "店の外",
        "外に出",
        "移動した",
        "歩き出",
        "向かった",
        "場面",
    )
    visual_markers = (
        "見せて",
        "画像",
        "絵",
        "写真",
        "生成",
        "着て",
        "ポーズ",
        "背景",
        "event cg",
        "cg",
    )
    if any(marker in text for marker in visual_markers) or any(marker in lowered for marker in visual_markers):
        return {"intent": "visual_request", "reason": "visual wording detected", "should_generate_image": True}
    if any(marker in text for marker in narration_markers):
        return {"intent": "narration", "reason": "scene direction wording detected", "should_generate_image": True}
    return {"intent": "dialogue", "reason": "normal player dialogue", "should_generate_image": False}


def build_narration_scene_prompt(context: dict, user_message_text: str, intent: dict) -> str:
    state_json = context["state"].get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    lines = [
        "You are the stage director for a live visual novel.",
        "The latest input is not normal dialogue. Convert it into a visual scene update.",
        "Return only a JSON object.",
        "Required keys: scene_phase, location, background, focus_summary, next_topic, transition_occurred, character_reaction_hint, image_focus.",
        "Make the result concrete enough for image generation.",
        "Do not include the player as a visible person in the image.",
        "Prefer a dramatic visual-novel event CG moment, not a generic hallway/corridor.",
        f"Intent: {intent.get('intent')}",
        f"Intent reason: {intent.get('reason') or ''}",
        f"Project: {context['project'].get('title') or 'Untitled'}",
        f"World: {context['world'].get('overview') or context['world'].get('name') or ''}",
        f"Current location: {state_json.get('location') or scene_progression.get('location') or ''}",
        f"Current background: {state_json.get('background') or scene_progression.get('background') or ''}",
        "Characters:",
    ]
    for character in context["characters"]:
        lines.append(
            f"- {character.get('name')}: appearance={character.get('appearance_summary') or ''}, personality={character.get('personality') or ''}"
        )
    lines.append("Recent conversation:")
    for message in context["messages"][-8:]:
        lines.append(f"- {message.get('speaker_name') or message.get('sender_type')}: {message.get('message_text')}")
    lines.append(f"Scene direction from player: {user_message_text}")
    return "\n".join(lines)


def fallback_narration_scene(context: dict, user_message_text: str, intent: dict) -> dict:
    state_json = dict(context["state"].get("state_json") or {})
    current = dict(state_json.get("scene_progression") or {})
    text = str(user_message_text or "").strip()
    location = current.get("location") or state_json.get("location") or context["world"].get("name")
    background = current.get("background") or state_json.get("background")
    if "店の外" in text or "外に出" in text:
        location = "店の外"
        background = "店の外の歩道、街明かりが服を照らしている"
    return {
        "scene_phase": "directed_scene",
        "location": location,
        "background": background,
        "focus_summary": text or "場面が切り替わった",
        "next_topic": "新しい場面へのキャラクターの反応",
        "transition_occurred": True,
        "character_reaction_hint": "新しい場面や服装を見せながら、短く魅力的に反応する",
        "image_focus": text or "新しい場面のイベントCG",
    }


def build_narration_reaction_prompt(context: dict, user_message_text: str, scene_update: dict) -> str:
    lines = [
        "You write one short spoken reaction after a visual scene transition in a live visual novel.",
        "Return only a JSON object.",
        "Required keys: speaker_name, message_text.",
        "speaker_name must be one of the active characters.",
        "message_text must be a short spoken line only. No narration.",
        "The character should react to the new scene as if the image has just changed.",
        "Make it feel like a visual novel event CG moment.",
        "Do not explain that a scene changed.",
        f"Player name: {context['session'].get('player_name') or 'あなた'}",
        f"Scene direction: {user_message_text}",
        f"New location: {scene_update.get('location') or ''}",
        f"New background: {scene_update.get('background') or ''}",
        f"Scene focus: {scene_update.get('focus_summary') or ''}",
        f"Reaction hint: {scene_update.get('character_reaction_hint') or ''}",
        "Characters:",
    ]
    for character in context["characters"]:
        lines.append(
            f"- {character.get('name')}: first_person={character.get('first_person') or ''}, second_person={character.get('second_person') or ''}, personality={character.get('personality') or ''}, speech_style={character.get('speech_style') or ''}, sample={character.get('speech_sample') or ''}"
        )
    return "\n".join(lines)


def fallback_narration_reaction(context: dict, scene_update: dict) -> dict:
    speaker = context["characters"][0]["name"] if context["characters"] else "Character"
    if scene_update.get("location"):
        message = f"どう？　ここだと、少し違って見えるでしょう？"
    else:
        message = "どう？　今のわたし、ちゃんと見てくれてる？"
    return {"speaker_name": speaker, "message_text": message}


def build_scene_choice_prompt(context: dict, speaker_name: str, message_text: str) -> str:
    state_json = context["state"].get("state_json") or {}
    displayed_image = state_json.get("displayed_image_observation") or {}
    scene_progression = state_json.get("scene_progression") or {}
    session_objective = get_session_objective(context)
    lines = [
        "You extract optional visual-novel choice buttons from the latest character line.",
        "Return only a JSON object.",
        "Required keys: should_show_choices, choices.",
        "choices must be an array of 0 to 2 items.",
        "Each choice requires: label, intent, scene_instruction, image_prompt_hint, reply_hint.",
        "Show choices only when the character line naturally offers or implies a player-selectable action, location change, visual event, or topic branch.",
        "Do not create choices for simple acknowledgements, exposition, or actions the character has already completed.",
        "Labels must be short natural Japanese button text such as 海へ行く, 山へ行く, 夜景を見る.",
        "scene_instruction and reply_hint must be Japanese.",
        "Avoid unsafe, coercive, or character-NG actions.",
        f"Player name: {context['session'].get('player_name') or 'プレイヤー'}",
        f"Session objective: {session_objective or 'none'}",
        f"Current location: {state_json.get('location') or scene_progression.get('location') or ''}",
        f"Current background: {state_json.get('background') or scene_progression.get('background') or ''}",
        f"Displayed image summary: {displayed_image.get('short_summary') or ''}",
        "Characters:",
    ]
    for character in context["characters"]:
        lines.append(
            f"- {character.get('name')}: personality={character.get('personality') or ''}, speech_style={character.get('speech_style') or ''}, ng_rules={character.get('ng_rules') or ''}"
        )
    lines.append("Recent conversation:")
    for message in context["messages"][-8:]:
        lines.append(f"- {message.get('speaker_name') or message.get('sender_type')}: {message.get('message_text')}")
    lines.append("Latest character line:")
    lines.append(f"- {speaker_name}: {message_text}")
    lines.append("If the line mentions multiple possible destinations such as sea and mountain, create one choice for each.")
    return "\n".join(lines)


def fallback_scene_choices(context: dict, speaker_name: str, message_text: str) -> dict:
    text = str(message_text or "")
    candidates = []
    keyword_map = [
        ("海", "海へ行く", "キャラクターと一緒に海へ移動する。海辺に到着した開放的な場面を生成する。", "海辺、波、空、キャラクターがこちらを見る"),
        ("山", "山へ行く", "キャラクターと一緒に山へ移動する。自然の中で空気が変わる場面を生成する。", "山道、森、自然、キャラクターがこちらを見る"),
        ("夜景", "夜景を見る", "キャラクターと一緒に夜景が見える場所へ移動する。きらめく夜景を眺める場面を生成する。", "夜景、都市の光、ロマンチックな空気"),
        ("店", "店に入る", "キャラクターと一緒に店内へ入る。店の雰囲気が伝わる場面を生成する。", "店内、商品棚、柔らかい照明"),
        ("クルーザー", "クルーザーを見る", "キャラクターと一緒にクルーザーが見える場所へ移動する。クルーザーを印象的に見せる場面を生成する。", "港、クルーザー、水面、キャラクター"),
    ]
    for keyword, label, instruction, hint in keyword_map:
        if keyword in text and label not in {item["label"] for item in candidates}:
            candidates.append(
                {
                    "id": f"choice_{len(candidates) + 1}",
                    "label": label,
                    "intent": "scene_transition",
                    "scene_instruction": instruction,
                    "image_prompt_hint": hint,
                    "reply_hint": f"{label}後、{speaker_name or 'キャラクター'}がその場面に合う短い一言を話す。",
                }
            )
        if len(candidates) >= 2:
            break
    return {"should_show_choices": bool(candidates), "choices": candidates}


def build_costume_rewrite_prompt(context: dict, character: dict, instruction: str, costume_context: str) -> str:
    lines = [
        "You rewrite a user's costume request for an image-to-image character reference generator.",
        "Return only a JSON object.",
        "Required keys: rewritten_instruction, safety_note, negative_note.",
        "The original user instruction is the highest priority. Character personality and context may only add motifs; they must not replace the requested outfit category.",
        "The rewritten_instruction must preserve the user's requested outfit category and current conversation context.",
        "Do not over-sanitize into unrelated clothing. If the user asks for swimwear in a beach/sea context, keep it clearly as swimwear or water-ready beachwear, not ordinary summer clothes, workwear, or fisher clothing.",
        "If the original instruction contains swimwear, swimsuit, bikini, 水着, ビキニ, or beachwear, the rewritten_instruction must explicitly include stylish swimwear, one-piece swimsuit, sporty two-piece swim set, or water-ready beachwear.",
        "Do not reinterpret swimwear as a business outfit, fantasy dress, armor, regular summer clothes, or character-theme costume. Character motifs can be reflected in colors, accessories, trim, or styling only.",
        "This is for a visual novel character costume variation. Keep tasteful heroine appeal, glamour, charm, and moderate stylish sexiness when the user implies it.",
        "If the user's wording is too explicit, translate it into safe fashion and character-design language instead of deleting the appeal.",
        "Express attractiveness through silhouette, color, fabric texture, styling, confidence, and elegant pose direction.",
        "Make the wording safe for a general-audience image model: no nude wording, no explicit sexual acts, no body-part fetish emphasis, no transparent clothing emphasis, no childlike wording.",
        "Use tasteful fashion language: stylish swimwear, resort swimwear, one-piece swimsuit, sporty two-piece swim set, beachwear, elegant, glamorous, cute, mature, coordinated, heroine-like.",
        "The output should describe clothing only, not a full scene illustration.",
        "Japanese output is preferred.",
        f"Original user instruction: {instruction}",
        f"Character: name={character.get('name') or ''}, gender={character.get('gender') or ''}, personality={character.get('personality') or ''}, art_style={character.get('art_style') or ''}",
        "Conversation and current scene context:",
        costume_context,
    ]
    return "\n".join(lines)


def fallback_costume_rewrite(instruction: str) -> dict:
    text = str(instruction or "").strip()
    lowered = text.lower()
    if any(token in lowered for token in ("水着", "ビキニ", "swimsuit", "bikini")):
        rewritten = (
            "海辺やリゾート場面に合う、ノベルゲームのヒロインらしい華やかなビーチ用スイムウェア。"
            "キャラクターの雰囲気に合わせ、かわいさ、大人っぽさ、適度な色気をファッションとして上品に表現する。"
            "シルエット、色、素材感、アクセサリー、パレオや薄手の羽織りなどで魅力的にコーディネートする。"
        )
        return {
            "rewritten_instruction": rewritten,
            "safety_note": "露骨な性的表現ではなく、衣装デザイン、シルエット、色味、質感、雰囲気で魅力を出す。",
            "negative_note": "裸体、性的行為、局部や胸部の過度な強調、透け表現の強調、幼く見える表現は禁止。",
        }
    return {
        "rewritten_instruction": text,
        "safety_note": "ノベルゲームの衣装差分として、華やかさや魅力をファッション表現で自然に出す。",
        "negative_note": "裸体、性的行為、局部や胸部の過度な強調、透け表現の強調、幼く見える表現は禁止。",
    }


def build_image_prompt_safety_rewrite_prompt(context: dict, prompt: str, purpose: str = "live_scene") -> str:
    state_json = (context.get("state") or {}).get("state_json") or {}
    room = context.get("room") or {}
    lines = [
        "You are an image prompt safety editor for a live visual novel image generator.",
        "Return only a JSON object.",
        "Required keys: rewritten_prompt, changed, safety_reason.",
        "Rewrite the image prompt before it is sent to the image API.",
        "The Original image prompt is the highest priority. Use project/session context only to preserve character identity and art continuity, not to replace the requested scene, location, outfit, or action.",
        "Never replace a requested beach/sea/pool/summer scene with the current session location or a previous scene.",
        "If the prompt might be classified as sexual, especially due to beach/swimwear/young-looking/body/wet/close-up wording, rewrite it into safer visual language without changing the requested outfit category.",
        "Do not use a fixed template. Preserve the user's scene intent, character identity, story context, outfit direction, mood, and visual appeal.",
        "Avoid explicit or policy-triggering wording such as bikini, revealing, sexy, sensual, erotic, wet skin, chest, hips, body emphasis, young girl, 20 years old, close-up body framing.",
        "If the original asks for swimwear, keep swimwear: prefer one-piece swimsuit, stylish resort swimwear, sporty two-piece swim set, coordinated swim set with skirted bottom, beach cover-up as an accessory, or water-ready beachwear. Do not downgrade it to generic summer clothes.",
        "For a prompt like 'summer sea, happily playing in swimwear', the rewritten prompt must still depict the character at the summer sea, happily playing, wearing clearly recognizable stylish swimwear.",
        "Prefer natural image-generation language such as adult woman in her mid-20s or older, cheerful summer vacation, stylish swimwear with tasteful coverage, sunlit ocean, joyful expression, energetic movement, editorial beach fashion, tasteful visual novel event CG.",
        "If the prompt is already safe, keep it mostly unchanged and set changed=false.",
        "Never add captions, text, speech bubbles, UI, logo, or watermark.",
        f"Purpose: {purpose}",
        f"Project: {(context.get('project') or {}).get('title') or ''}",
        f"Room objective, for tone only: {room.get('conversation_objective') or ''}",
        "Characters:",
    ]
    for character in context.get("characters") or []:
        lines.append(
            f"- {character.get('name')}: gender={character.get('gender') or ''}, identity/appearance notes={character.get('appearance_summary') or ''}, personality={character.get('personality') or ''}, art_style={character.get('art_style') or ''}"
        )
    lines.extend(
        [
            "Original image prompt:",
            str(prompt or ""),
        ]
    )
    return "\n".join(lines)


def fallback_image_prompt_safety_rewrite(prompt: str) -> dict:
    return {
        "rewritten_prompt": str(prompt or ""),
        "changed": False,
        "safety_reason": "AI safety rewrite unavailable; using original prompt.",
    }


def build_line_visual_note_prompt(context: dict, speaker_name: str, message_text: str) -> str:
    state_json = context["state"].get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    lines = [
        "You are a scene-to-image bridge for a live visual novel.",
        "Convert the latest spoken line into a compact visual note for the image generator.",
        "Return only a JSON object.",
        "Required keys: location, background, expression, pose, camera, focus_object, scene_moment.",
        "Assume first-person player viewpoint.",
        f"Current location: {scene_progression.get('location') or state_json.get('location') or ''}",
        f"Current background: {scene_progression.get('background') or state_json.get('background') or ''}",
        f"Scene summary: {scene_progression.get('focus_summary') or state_json.get('focus_summary') or ''}",
        f"Speaker: {speaker_name}",
        f"Latest line: {message_text}",
    ]
    return "\n".join(lines)


def fallback_line_visual_note(context: dict, speaker_name: str, message_text: str) -> dict:
    state_json = context["state"].get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    text = str(message_text or "")
    lowered = text.lower()
    focus_object = None
    if "クルーザー" in text or "cruiser" in lowered:
        focus_object = "cruiser"
    elif "街" in text or "city" in lowered:
        focus_object = "city view"
    elif "港" in text or "harbor" in lowered:
        focus_object = "harbor"
    return {
        "location": scene_progression.get("location") or state_json.get("location"),
        "background": scene_progression.get("background") or state_json.get("background"),
        "expression": state_json.get("expression") or "neutral",
        "pose": state_json.get("pose") or "conversation",
        "camera": state_json.get("camera") or ("wide shot" if focus_object else "medium shot"),
        "focus_object": focus_object,
        "scene_moment": f"{speaker_name} speaking this line in the current scene: {text[:120]}",
    }


def build_session_memory(messages: list[dict], current_state_json: dict | None) -> dict:
    current_state_json = dict(current_state_json or {})
    previous_memory = dict(current_state_json.get("session_memory") or {})
    recent_topics = []
    player_preferences = previous_memory.get("player_preferences")
    relationship_notes = previous_memory.get("relationship_notes")
    previous_character_memories = dict(previous_memory.get("character_memories") or {})
    character_memories = {
        name: _normalize_memory_profile(memory)
        for name, memory in previous_character_memories.items()
        if isinstance(memory, dict)
    }

    for message in messages[-8:]:
        text = (message.get("message_text") or "").strip()
        if not text:
            continue
        if message.get("sender_type") == "user":
            recent_topics.append(text[:50])
            lowered = text.lower()
            if any(keyword in text for keyword in ("好き", "嫌い", "欲しい", "詳しく", "興味", "趣味")) or any(
                keyword in lowered for keyword in ("like", "dislike", "prefer", "want", "hobby")
            ):
                player_preferences = text[:120]
        elif message.get("sender_type") == "character":
            if any(keyword in text for keyword in ("好き", "嫌い", "苦手", "趣味", "嬉しい", "恋", "惹かれる")):
                relationship_notes = text[:120]
            speaker_name = str(message.get("speaker_name") or "").strip()
            if speaker_name:
                memory_entry = _normalize_memory_profile(character_memories.get(speaker_name) or {})
                memory_entry["likes"] = _merge_lists(memory_entry["likes"], _extract_likes(text))
                memory_entry["dislikes"] = _merge_lists(memory_entry["dislikes"], _extract_dislikes(text))
                memory_entry["hobbies"] = _merge_lists(memory_entry["hobbies"], _extract_hobbies(text))
                memory_entry["taboos"] = _merge_lists(memory_entry["taboos"], _extract_taboos(text))
                note = _extract_character_memory_note(text)
                if note:
                    memory_entry["memorable_events"] = _merge_lists(memory_entry["memorable_events"], [note])
                romance = _extract_romance_preferences(text)
                for key in ROMANCE_KEYS:
                    memory_entry["romance_preferences"][key] = _merge_lists(
                        memory_entry["romance_preferences"][key],
                        romance.get(key) or [],
                    )
                character_memories[speaker_name] = memory_entry

    memory = {
        "recent_topics": " / ".join(recent_topics[-3:]) if recent_topics else previous_memory.get("recent_topics"),
        "player_preferences": player_preferences,
        "relationship_notes": relationship_notes,
        "character_memories": {
            name: value
            for name, value in character_memories.items()
            if any(value.get(key) for key in MEMORY_CATEGORIES)
            or any((value.get("romance_preferences") or {}).get(key) for key in ROMANCE_KEYS)
        },
        "last_updated_at": datetime.utcnow().isoformat(),
    }
    return {key: value for key, value in memory.items() if value}


def build_conversation_evaluation_prompt(context: dict) -> str:
    session_objective = get_session_objective(context)
    state_json = context["state"].get("state_json") or {}
    relationship_state = state_json.get("relationship_state") or {}
    memory_match = _analyze_player_memory_match(context)
    lines = [
        "You are evaluating progress in a live visual novel conversation.",
        "Return only a JSON object.",
        "Required keys: score, label, reason, mood, theme.",
        "score must be an integer from 0 to 100.",
        "theme must be either romance or general.",
        "label, reason, and mood must be written in natural Japanese.",
        "reason must be 1 to 2 short Japanese sentences.",
        "Do not write English words or English sentences in reason.",
        f"Session objective: {session_objective or 'none'}",
        "Recent conversation:",
    ]
    for message in context["messages"][-10:]:
        lines.append(f"- {message.get('speaker_name') or message.get('sender_type')}: {message.get('message_text')}")
    if relationship_state:
        lines.append("Relationship state:")
        for name, metrics in relationship_state.items():
            if isinstance(metrics, dict):
                lines.append(
                    f"- {name}: affection={metrics.get('affection', 0)}, interest={metrics.get('interest', 0)}, trust={metrics.get('trust', 0)}, tension={metrics.get('tension', 0)}"
                )
    session_memory_map = ((context.get("state") or {}).get("state_json") or {}).get("session_memory", {}).get("character_memories") or {}
    for character in context.get("characters") or []:
        summary = _build_character_memory_summary(_flatten_character_memory(character, session_memory_map))
        if summary:
            lines.append(f"- {character.get('name')}: {summary}")
    if memory_match["reasons"]:
        lines.append(f"Memory match analysis: {', '.join(memory_match['reasons'])}")
    lines.append("Increase the score when the player matches likes, hobbies, or romantic preferences.")
    lines.append("Decrease the score when the player hits dislikes, taboos, or boundaries.")
    return "\n".join(lines)


def fallback_conversation_evaluation(context: dict) -> dict:
    objective = get_session_objective(context) or ""
    state_json = context["state"].get("state_json") or {}
    relationship_state = state_json.get("relationship_state") or {}
    score = 18
    mood = "導入段階"
    label = "進捗"
    theme = "general"
    if any(token in objective for token in ("恋愛", "好き", "惚れ", "感情")):
        label = "恋愛進捗"
        theme = "romance"
        metrics = next((value for value in relationship_state.values() if isinstance(value, dict)), {})
        score = max(
            0,
            min(
                100,
                int((metrics.get("affection", 0) * 0.45) + (metrics.get("interest", 0) * 0.35) + (metrics.get("trust", 0) * 0.2)),
            ),
        )
        mood = "恋愛の熱が高まりつつある" if score >= 45 else "少しずつ距離が縮まっている"
    elif objective:
        label = "関心進捗"
        metrics = next((value for value in relationship_state.values() if isinstance(value, dict)), {})
        score = max(0, min(100, int((metrics.get("interest", 0) * 0.6) + (metrics.get("trust", 0) * 0.2) + 10)))
        mood = "関心が高まっている" if score >= 40 else "探り合いの段階"
    memory_match = _analyze_player_memory_match(context)
    score = max(0, min(100, score + memory_match["bonus"] - memory_match["penalty"]))
    if memory_match["penalty"] > 0:
        mood = "少し警戒している"
    elif memory_match["bonus"] > 0 and theme == "romance":
        mood = "気持ちがやわらいでいる"
    reason = "直近の会話内容と関係性の状態から、現在の進み具合を評価しています。"
    if memory_match["reasons"]:
        reason = f"{reason} 記憶要素: {', '.join(memory_match['reasons'])}。"
    return {
        "score": score,
        "label": label,
        "reason": reason,
        "mood": mood,
        "theme": theme,
    }


def build_conversation_director_prompt(context: dict, user_message_text: str) -> str:
    session_objective = get_session_objective(context)
    state_json = context["state"].get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    relationship_state = state_json.get("relationship_state") or {}
    conversation_evaluation = state_json.get("conversation_evaluation") or {}
    memory_match = _analyze_player_memory_match(context)
    lines = [
        "You are the conversation director for a live visual novel.",
        "Return only a JSON object.",
        "Required keys: turn_intent, emotional_tone, relationship_goal, scene_goal, must_include, avoid.",
        "turn_intent must be one of: invite, tease, reveal, test, comfort, escalate, explain, guide.",
        f"Project: {context['project'].get('title') or 'Untitled'}",
        f"World: {context['world'].get('overview') or context['world'].get('name') or ''}",
        f"Current phase: {scene_progression.get('scene_phase') or ''}",
        f"Current focus: {scene_progression.get('focus_summary') or ''}",
        f"Next topic: {scene_progression.get('next_topic') or ''}",
    ]
    if session_objective:
        lines.append(f"Session objective: {session_objective}")
    if relationship_state:
        lines.append("Relationship state:")
        for name, metrics in relationship_state.items():
            if isinstance(metrics, dict):
                lines.append(
                    f"- {name}: affection={metrics.get('affection', 0)}, interest={metrics.get('interest', 0)}, trust={metrics.get('trust', 0)}, tension={metrics.get('tension', 0)}"
                )
    if conversation_evaluation:
        lines.append("Conversation evaluation:")
        lines.append(f"- score={conversation_evaluation.get('score')}")
        lines.append(f"- label={conversation_evaluation.get('label') or ''}")
        lines.append(f"- theme={conversation_evaluation.get('theme') or ''}")
        lines.append(f"- mood={conversation_evaluation.get('mood') or ''}")
        score = _conversation_score(conversation_evaluation)
        is_romance = _is_romance_goal(session_objective, conversation_evaluation)
        if score is not None and score <= 35:
            lines.append(
                "Director strategy: progress is low. Do not choose a passive or purely explanatory turn. "
                "Choose invite, comfort, reveal, or tease and give the character a concrete recovery move."
            )
            if is_romance:
                lines.append(
                    "Romance recovery: the character should make the player feel personally noticed, "
                    "show a tiny vulnerability or playful affection, and invite a response that can raise affection/trust."
                )
            else:
                lines.append(
                    "Objective recovery: make the session objective feel appealing, specific, and easy for the player to engage with."
                )
        elif score is not None and score <= 65:
            lines.append(
                "Director strategy: progress is moderate. Reward the player's useful input and steer to a more specific next beat."
            )
        elif score is not None and score >= 80:
            lines.append(
                "Director strategy: progress is high. Escalate emotional intimacy or commitment toward the session objective."
            )
    if memory_match["reasons"]:
        lines.append(f"Memory match analysis: {', '.join(memory_match['reasons'])}")
    lines.append("Characters:")
    session_memory_map = ((context.get("state") or {}).get("state_json") or {}).get("session_memory", {}).get("character_memories") or {}
    for character in context["characters"]:
        lines.append(
            f"- {character['name']}: nickname={character.get('nickname') or ''}, gender={character.get('gender') or ''}, personality={character.get('personality') or ''}, speech_style={character.get('speech_style') or ''}, speech_sample={character.get('speech_sample') or ''}"
        )
        summary = _build_character_memory_summary(_flatten_character_memory(character, session_memory_map))
        if summary:
            lines.append(f"  memory={summary}")
    lines.append("Recent conversation:")
    for message in context["messages"][-8:]:
        lines.append(f"- {message.get('speaker_name') or message.get('sender_type')}: {message.get('message_text')}")
    lines.append(f"- player: {user_message_text}")
    lines.append("Avoid repeating guide-like movement offers. The director must add a fresh emotional or dramatic beat.")
    return "\n".join(lines)


def fallback_conversation_director(context: dict, user_message_text: str) -> dict:
    state_json = context["state"].get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    conversation_evaluation = state_json.get("conversation_evaluation") or {}
    score = _conversation_score(conversation_evaluation)
    is_romance = _is_romance_goal(get_session_objective(context), conversation_evaluation)
    lowered = str(user_message_text or "").lower()
    memory_match = _analyze_player_memory_match(context)
    if memory_match["penalty"] > 0:
        return {
            "turn_intent": "test",
            "emotional_tone": "cool and guarded",
            "relationship_goal": "create distance after the player touched a dislike or taboo",
            "scene_goal": scene_progression.get("next_topic") or "redirect the conversation carefully",
            "must_include": ["a cooler reaction", "a subtle boundary signal"],
            "avoid": ["warm approval", "acting unaffected"],
        }
    if memory_match["bonus"] > 0:
        return {
            "turn_intent": "escalate",
            "emotional_tone": "pleased and softer",
            "relationship_goal": "reward the player for remembering something important",
            "scene_goal": scene_progression.get("next_topic") or "deepen the emotional exchange",
            "must_include": ["warm appreciation", "one emotionally closer reaction"],
            "avoid": ["flat acknowledgment", "forgetting the matched preference"],
        }
    if score is not None and score <= 35:
        if is_romance:
            return {
                "turn_intent": "tease",
                "emotional_tone": "softly proactive and inviting",
                "relationship_goal": "recover low romantic progress by making the player feel personally noticed",
                "scene_goal": scene_progression.get("next_topic") or "create a warmer emotional opening",
                "must_include": ["one small personal disclosure", "one easy affectionate question or invitation"],
                "avoid": ["passive waiting", "guide-like explanations", "generic acknowledgement"],
            }
        return {
            "turn_intent": "invite",
            "emotional_tone": "proactive and engaging",
            "relationship_goal": "recover low progress by making the objective easier and more attractive to answer",
            "scene_goal": scene_progression.get("next_topic") or "offer a concrete next hook",
            "must_include": ["one specific hook", "one reason the player should care"],
            "avoid": ["passive waiting", "empty acknowledgement", "vague explanation"],
        }
    if score is not None and score <= 65:
        return {
            "turn_intent": "reveal",
            "emotional_tone": "warm and momentum-building",
            "relationship_goal": "turn the player's input into stronger interest and trust",
            "scene_goal": scene_progression.get("next_topic") or "deepen the current topic",
            "must_include": ["one new concrete detail", "one question that advances the objective"],
            "avoid": ["stalling", "repeating the same offer"],
        }
    if is_affirmative_progress_message(user_message_text):
        return {
            "turn_intent": "guide",
            "emotional_tone": "warmly leading",
            "relationship_goal": "increase trust by guiding the player forward",
            "scene_goal": scene_progression.get("next_topic") or "advance the scene",
            "must_include": ["one concrete next-step description", "one line that makes the player feel accompanied"],
            "avoid": ["passive repetition", "empty acknowledgment"],
        }
    if any(keyword in lowered for keyword in ("why", "how", "what", "where", "なぜ", "なんで", "どうして", "どこ", "何")):
        return {
            "turn_intent": "reveal",
            "emotional_tone": "engaging and informative",
            "relationship_goal": "build interest by revealing one concrete detail",
            "scene_goal": scene_progression.get("next_topic") or "reveal the next detail",
            "must_include": ["one new concrete detail", "one hook into the next topic"],
            "avoid": ["vague explanation only"],
        }
    return {
        "turn_intent": "invite",
        "emotional_tone": "lightly engaging",
        "relationship_goal": "keep the player emotionally engaged",
        "scene_goal": scene_progression.get("next_topic") or "continue the conversation",
        "must_include": ["one small forward pull"],
        "avoid": ["pure acknowledgment"],
    }


def apply_director_relationship_update(relationship_state: dict, context: dict, director: dict) -> dict:
    active_names = [character["name"] for character in context["characters"][:2]]
    if not active_names:
        return relationship_state
    turn_intent = str(director.get("turn_intent") or "")
    deltas = {"affection": 0, "interest": 0, "trust": 0, "tension": 0}
    if turn_intent in {"invite", "comfort", "guide"}:
        deltas["trust"] += 1
        deltas["interest"] += 1
    if turn_intent in {"tease", "escalate"}:
        deltas["affection"] += 1
        deltas["tension"] += 1
        deltas["interest"] += 1
    if turn_intent in {"reveal", "explain"}:
        deltas["interest"] += 2
    if turn_intent == "test":
        deltas["tension"] += 1
        deltas["interest"] += 1
    for name in active_names:
        current = dict(relationship_state.get(name) or {})
        current.setdefault("affection", 0)
        current.setdefault("interest", 0)
        current.setdefault("trust", 0)
        current.setdefault("tension", 0)
        for key, delta in deltas.items():
            current[key] = max(0, min(100, int(current.get(key, 0)) + delta))
        relationship_state[name] = current
    return relationship_state


def build_scene_progression_prompt(context: dict, user_message_text: str) -> str:
    state_json = context["state"].get("state_json") or {}
    progression = state_json.get("scene_progression") or {}
    lines = [
        "You are the scene progression planner for a live visual novel conversation.",
        "Read the latest player input and decide how the visible scene should progress.",
        "Return only a JSON object.",
        "Required keys: scene_phase, location, background, focus_summary, next_topic, transition_occurred.",
        "If the player agrees to move, see, follow, or be guided, advance the scene instead of keeping it in the same pre-move state.",
        "Do not keep repeating the same pending transition.",
        f"Project: {context['project'].get('title') or 'Untitled'}",
        f"World: {context['world'].get('overview') or context['world'].get('name') or ''}",
        f"Current location: {state_json.get('location') or progression.get('location') or ''}",
        f"Current phase: {progression.get('scene_phase') or ''}",
        f"Current next_topic: {progression.get('next_topic') or ''}",
        "Recent conversation:",
    ]
    for message in context["messages"][-8:]:
        lines.append(f"- {message.get('speaker_name') or message.get('sender_type')}: {message.get('message_text')}")
    lines.append(f"- player: {user_message_text}")
    return "\n".join(lines)


def fallback_scene_progression(context: dict, user_message_text: str) -> dict:
    state_json = dict(context["state"].get("state_json") or {})
    current = dict(state_json.get("scene_progression") or {})
    lowered = user_message_text.lower()
    if is_affirmative_progress_message(user_message_text):
        if "クルーザー" in user_message_text:
            return {
                "scene_phase": "arrival_showcase",
                "location": state_json.get("location") or "harbor",
                "background": "night harbor with cruiser",
                "focus_summary": "The conversation shifts toward the cruiser as a visible point of focus.",
                "next_topic": "explain the cruiser",
                "transition_occurred": True,
            }
        if "街" in user_message_text or "city" in lowered:
            city_name = context["world"].get("name") or "the city"
            return {
                "scene_phase": "city_arrival",
                "location": f"{city_name} entrance",
                "background": f"entrance view of {city_name}",
                "focus_summary": "The visible scene advances to the city entrance.",
                "next_topic": "explain the city",
                "transition_occurred": True,
            }
        return {
            "scene_phase": "progressed",
            "location": current.get("location") or state_json.get("location") or context["world"].get("name"),
            "background": current.get("background") or state_json.get("background"),
            "focus_summary": "The conversation advances into the next visible part of the scene.",
            "next_topic": current.get("next_topic") or "describe the next sight",
            "transition_occurred": True,
        }
    return {
        "scene_phase": current.get("scene_phase") or "conversation",
        "location": current.get("location") or state_json.get("location") or context["world"].get("name"),
        "background": current.get("background") or state_json.get("background"),
        "focus_summary": current.get("focus_summary") or state_json.get("focus_summary") or "ongoing conversation",
        "next_topic": current.get("next_topic") or "continue the conversation",
        "transition_occurred": False,
    }
