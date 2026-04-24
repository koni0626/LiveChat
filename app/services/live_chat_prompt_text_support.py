from __future__ import annotations

from datetime import datetime


def get_session_objective(context: dict) -> str | None:
    session_settings = context.get("session", {}).get("settings_json") or {}
    if isinstance(session_settings, dict):
        value = str(
            session_settings.get("conversation_objective")
            or session_settings.get("session_objective")
            or ""
        ).strip()
        return value or None
    return None


def build_opening_prompt(context: dict) -> str:
    session_objective = get_session_objective(context)
    state_json = (context.get("state") or {}).get("state_json") or {}
    relationship_state = state_json.get("relationship_state") or {}
    lines = [
        "あなたはライブ会話モードのキャラクターです。",
        "セッション開始時の最初の一言を自然な日本語で作成してください。",
        "返答は JSON object のみです。",
        "キーは speaker_name, message_text の2つです。",
        "speaker_name は実際に話すキャラクター名にしてください。",
        "message_text は最初の挨拶として自然で短すぎず長すぎない一言にしてください。",
        "いきなり案内や説明を始めず、まずは挨拶・呼びかけ・会話のきっかけを優先してください。",
        "『こんにちは』『はじめまして』『今日は何のお話をする？』のような自然な導入は歓迎です。",
        "プレイヤーを惹きつける空気感は保ちつつ、不自然に目的を露骨に言わないでください。",
        "Character personality must strongly shape the tone, reactions, emotional nuance, and distance in conversation.",
        "Do not flatten every character into a generic guide. Even if the role is guide, keep the character's personality vivid.",
        "",
        f"作品名: {context['project'].get('title') or 'Untitled'}",
        f"プレイヤー名: {context['session'].get('player_name') or context['story_outline'].get('protagonist_name') or 'プレイヤー'}",
    ]
    if session_objective:
        lines.append(f"Session objective: {session_objective}")
        lines.append("Make the opening line lightly align with this objective, but keep it natural and conversational.")
    if context["world"].get("overview"):
        lines.append(f"世界観: {context['world']['overview']}")
    if context["story_outline"].get("premise"):
        lines.append(f"物語の前提: {context['story_outline']['premise']}")
    if relationship_state:
        lines.append("Relationship state:")
        for name, metrics in relationship_state.items():
            if not isinstance(metrics, dict):
                continue
            metric_text = ", ".join(
                f"{key}={metrics.get(key)}"
                for key in ("affection", "interest", "trust", "tension")
                if metrics.get(key) is not None
            )
            if metric_text:
                lines.append(f"- {name}: {metric_text}")
    lines.append("キャラクター設定:")
    for character in context["characters"]:
        lines.append(
            f"- {character['name']}: role={character.get('role') or 'character'}, first_person={character.get('first_person') or ''}, second_person={character.get('second_person') or ''}, personality={character.get('personality') or ''}, speech_style={character.get('speech_style') or ''}, speech_sample={character.get('speech_sample') or ''}, ng_rules={character.get('ng_rules') or ''}"
        )
    return "\n".join(lines)


def fallback_opening_message(context: dict) -> dict:
    speaker = context["characters"][0]["name"] if context["characters"] else "キャラクター"
    player_name = context["session"].get("player_name") or context["story_outline"].get("protagonist_name") or "あなた"
    speech_style = context["characters"][0].get("speech_style") if context["characters"] else ""
    personality = context["characters"][0].get("personality") if context["characters"] else ""
    if any(token in str(speech_style) for token in ("砕け", "カジュアル")) or any(token in str(personality) for token in ("気さく", "明る", "フランク")):
        text = f"{player_name}、こんにちは。来てくれてうれしい。今日はどんな話から始めようか。"
    elif any(token in str(speech_style) for token in ("丁寧", "上品")) or any(token in str(personality) for token in ("穏やか", "優しい", "落ち着")):
        text = f"{player_name}さん、こんにちは。お会いできてうれしいです。今日はどんなお話をしましょうか。"
    else:
        text = f"{player_name}、こんにちは。来てくれてありがとう。今日は何から話そうか。"
    return {"speaker_name": speaker, "message_text": text}


def normalize_compare_text(text: str) -> str:
    value = str(text or "").strip()
    for token in ("。", "、", "！", "？", "…", "　", " ", "\n", "\r", "「", "」"):
        value = value.replace(token, "")
    return value


def is_affirmative_progress_message(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    positive_keywords = (
        "はい",
        "お願い",
        "お願いします",
        "分かった",
        "わかった",
        "行こう",
        "連れて行って",
        "見せて",
        "教えて",
        "ok",
        "okay",
        "sure",
        "yes",
    )
    return any(keyword in lowered for keyword in positive_keywords)


def recent_transition_offer_exists(context: dict) -> bool:
    transition_keywords = ("行こう", "見てみよう", "連れて行", "見せよう", "向かおう", "行ってみよう")
    for message in reversed(context["messages"][-4:]):
        if message.get("sender_type") != "character":
            continue
        text = str(message.get("message_text") or "")
        if any(keyword in text for keyword in transition_keywords):
            return True
    return False


def is_generic_transition_reply(text: str) -> bool:
    normalized = normalize_compare_text(text)
    generic_keywords = ("行こう", "ゆっくり行こう", "連れて行く", "急がなくていい", "見ていこう")
    return len(normalized) <= 32 and any(keyword in text for keyword in generic_keywords)


def build_reply_prompt(context: dict, user_message_text: str) -> str:
    session_objective = get_session_objective(context)
    state_json = context["state"].get("state_json") or {}
    session_memory = state_json.get("session_memory") or {}
    scene_progression = state_json.get("scene_progression") or {}
    conversation_director = state_json.get("conversation_director") or {}
    relationship_state = state_json.get("relationship_state") or {}
    visual_state = state_json.get("visual_state") or {}
    conversation_evaluation = state_json.get("conversation_evaluation") or {}
    lines = [
        "あなたはライブ会話モードの対話生成AIです。",
        "返答は JSON object のみです。",
        "キーは speaker_name, message_text の2つです。",
        "speaker_name は登場キャラクター名のみを使ってください。",
        "message_text はノベルゲームの1ターンとして自然な長さにしてください。",
        "会話を進め、次の情報・感情・関係性のどれかを前進させてください。",
        "受け身の相槌だけで終わらせないでください。",
        "",
        f"プレイヤー名: {context['session'].get('player_name') or context['story_outline'].get('protagonist_name') or '主人公'}",
    ]
    if session_objective:
        lines.append(f"Session objective: {session_objective}")
    if context["world"].get("overview"):
        lines.append(f"世界観: {context['world']['overview']}")
    if scene_progression:
        lines.append(f"現在フェーズ: {scene_progression.get('scene_phase') or ''}")
        lines.append(f"現在地: {scene_progression.get('location') or ''}")
        lines.append(f"場面要約: {scene_progression.get('focus_summary') or ''}")
        lines.append(f"次の話題: {scene_progression.get('next_topic') or ''}")
    if conversation_director:
        lines.append(f"Turn intent: {conversation_director.get('turn_intent') or ''}")
        lines.append(f"Emotional tone: {conversation_director.get('emotional_tone') or ''}")
        lines.append(f"Relationship goal: {conversation_director.get('relationship_goal') or ''}")
        lines.append(f"Scene goal: {conversation_director.get('scene_goal') or ''}")
    if visual_state:
        lines.append(f"Current visual location: {visual_state.get('location') or ''}")
        lines.append(f"Current visual background: {visual_state.get('background_details') or ''}")
    if conversation_evaluation:
        lines.append(f"Conversation progress score: {conversation_evaluation.get('score')}")
        lines.append(f"Conversation progress reason: {conversation_evaluation.get('reason') or ''}")
    if relationship_state:
        lines.append("Relationship state:")
        for name, metrics in relationship_state.items():
            if isinstance(metrics, dict):
                lines.append(
                    f"- {name}: affection={metrics.get('affection', 0)}, interest={metrics.get('interest', 0)}, trust={metrics.get('trust', 0)}, tension={metrics.get('tension', 0)}"
                )
    if session_memory.get("player_preferences"):
        lines.append(f"プレイヤー嗜好メモ: {session_memory['player_preferences']}")
    if session_memory.get("recent_topics"):
        lines.append(f"最近の話題: {session_memory['recent_topics']}")
    lines.append("登場キャラクター:")
    for character in context["characters"]:
        lines.append(
            f"- {character['name']}: role={character.get('role') or 'character'}, first_person={character.get('first_person') or ''}, second_person={character.get('second_person') or ''}, personality={character.get('personality') or ''}, speech_style={character.get('speech_style') or ''}, speech_sample={character.get('speech_sample') or ''}, ng_rules={character.get('ng_rules') or ''}"
        )
    lines.append("Recent conversation:")
    for message in context["messages"][-8:]:
        lines.append(f"- {message.get('speaker_name') or message.get('sender_type')}: {message.get('message_text')}")
    lines.append(f"- player: {user_message_text}")
    return "\n".join(lines)


def fallback_reply(context: dict, user_message_text: str) -> dict:
    speaker = context["characters"][0]["name"] if context["characters"] else "キャラクター"
    shortened = user_message_text[:40]
    return {
        "speaker_name": speaker,
        "message_text": f"{shortened}……うん、その話いいね。もう少し詳しく聞かせて。次の流れも一緒に決めよう。",
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

    for message in messages[-8:]:
        text = (message.get("message_text") or "").strip()
        if not text:
            continue
        if message.get("sender_type") == "user":
            recent_topics.append(text[:50])
            lowered = text.lower()
            if any(keyword in text for keyword in ("好き", "嫌い", "欲しい", "詳しく", "興味")) or any(keyword in lowered for keyword in ("like", "dislike", "prefer", "want")):
                player_preferences = text[:120]
        elif message.get("sender_type") == "character":
            if any(keyword in text for keyword in ("君", "あなた", "特別", "約束", "信頼", "距離")):
                relationship_notes = text[:120]

    memory = {
        "recent_topics": " / ".join(recent_topics[-3:]) if recent_topics else previous_memory.get("recent_topics"),
        "player_preferences": player_preferences,
        "relationship_notes": relationship_notes,
        "last_updated_at": datetime.utcnow().isoformat(),
    }
    return {key: value for key, value in memory.items() if value}


def build_conversation_evaluation_prompt(context: dict) -> str:
    session_objective = get_session_objective(context)
    state_json = context["state"].get("state_json") or {}
    relationship_state = state_json.get("relationship_state") or {}
    lines = [
        "You are evaluating progress in a live visual novel conversation.",
        "Return only a JSON object.",
        "Required keys: score, label, reason, mood, theme.",
        "score must be an integer from 0 to 100.",
        "theme must be either romance or general.",
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
    return "\n".join(lines)


def fallback_conversation_evaluation(context: dict) -> dict:
    objective = get_session_objective(context) or ""
    state_json = context["state"].get("state_json") or {}
    relationship_state = state_json.get("relationship_state") or {}
    score = 18
    mood = "gentle opening"
    label = "Progress"
    theme = "general"
    if any(token in objective for token in ("恋愛", "好き", "惚れ", "感情")):
        label = "Love Progress"
        theme = "romance"
        metrics = next((value for value in relationship_state.values() if isinstance(value, dict)), {})
        score = max(0, min(100, int((metrics.get("affection", 0) * 0.45) + (metrics.get("interest", 0) * 0.35) + (metrics.get("trust", 0) * 0.2))))
        mood = "romantic tension" if score >= 45 else "warming up"
    elif objective:
        label = "Interest Progress"
        metrics = next((value for value in relationship_state.values() if isinstance(value, dict)), {})
        score = max(0, min(100, int((metrics.get("interest", 0) * 0.6) + (metrics.get("trust", 0) * 0.2) + 10)))
        mood = "curious" if score >= 40 else "probing"
    return {
        "score": score,
        "label": label,
        "reason": "Current conversation progress was estimated from recent exchange and relationship state.",
        "mood": mood,
        "theme": theme,
    }


def build_conversation_director_prompt(context: dict, user_message_text: str) -> str:
    session_objective = get_session_objective(context)
    state_json = context["state"].get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    relationship_state = state_json.get("relationship_state") or {}
    conversation_evaluation = state_json.get("conversation_evaluation") or {}
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
    lines.append("Characters:")
    for character in context["characters"]:
        lines.append(
            f"- {character['name']}: role={character.get('role') or 'character'}, personality={character.get('personality') or ''}, speech_style={character.get('speech_style') or ''}, speech_sample={character.get('speech_sample') or ''}, is_guide={bool(character.get('is_guide'))}"
        )
    lines.append("Recent conversation:")
    for message in context["messages"][-8:]:
        lines.append(f"- {message.get('speaker_name') or message.get('sender_type')}: {message.get('message_text')}")
    lines.append(f"- player: {user_message_text}")
    return "\n".join(lines)


def fallback_conversation_director(context: dict, user_message_text: str) -> dict:
    state_json = context["state"].get("state_json") or {}
    scene_progression = state_json.get("scene_progression") or {}
    lowered = str(user_message_text or "").lower()
    if is_affirmative_progress_message(user_message_text):
        return {
            "turn_intent": "guide",
            "emotional_tone": "warmly leading",
            "relationship_goal": "increase trust by guiding the player forward",
            "scene_goal": scene_progression.get("next_topic") or "advance the scene",
            "must_include": ["one concrete next-step description", "one line that makes the player feel accompanied"],
            "avoid": ["passive repetition", "empty acknowledgment"],
        }
    if any(keyword in lowered for keyword in ("why", "how", "what", "where", "教えて", "なぜ", "どうして", "どこ", "何")):
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
                "focus_summary": "The guide leads the player to the cruiser and begins showing it up close.",
                "next_topic": "explain the cruiser",
                "transition_occurred": True,
            }
        if "街" in user_message_text or "city" in lowered:
            city_name = context["world"].get("name") or "the city"
            return {
                "scene_phase": "city_arrival",
                "location": f"{city_name} entrance",
                "background": f"entrance view of {city_name}",
                "focus_summary": "The guide arrives with the player at the city entrance and starts introducing the city.",
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
