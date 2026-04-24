from __future__ import annotations

from . import live_chat_prompt_support as prompt_support


def generate_opening_message(text_ai_client, context: dict) -> dict:
    try:
        prompt = prompt_support.build_opening_prompt(context)
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("opening generation response is invalid")
        speaker_name = str(parsed.get("speaker_name") or "").strip()
        message_text = str(parsed.get("message_text") or "").strip()
        allowed_names = {character["name"] for character in context["characters"]}
        if not speaker_name or speaker_name not in allowed_names:
            raise RuntimeError("opening speaker is invalid")
        if not message_text:
            raise RuntimeError("opening message is empty")
        return {"speaker_name": speaker_name, "message_text": message_text}
    except Exception:
        return prompt_support.fallback_opening_message(context)


def enforce_character_voice(context: dict, speaker_name: str, message_text: str) -> str:
    character = next((item for item in context["characters"] if item["name"] == speaker_name), None)
    if not character:
        return message_text
    first_person = str(character.get("first_person") or "").strip()
    if not first_person:
        return message_text
    replacements = {
        "僕": first_person,
        "ぼく": first_person,
        "ボク": first_person,
        "俺": first_person,
        "おれ": first_person,
    }
    for source, target in replacements.items():
        if target != source:
            message_text = message_text.replace(source, target)
    return message_text


def generate_reply(text_ai_client, context: dict, user_message_text: str) -> dict:
    try:
        prompt = prompt_support.build_reply_prompt(context, user_message_text)
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("reply generation response is invalid")
        speaker_name = str(parsed.get("speaker_name") or "").strip()
        message_text = str(parsed.get("message_text") or "").strip()
        allowed_names = {character["name"] for character in context["characters"]}
        if not speaker_name or speaker_name not in allowed_names:
            raise RuntimeError("reply speaker is invalid")
        if not message_text:
            raise RuntimeError("reply message is empty")
        message_text = enforce_character_voice(context, speaker_name, message_text)
        if prompt_support.is_affirmative_progress_message(user_message_text) and prompt_support.recent_transition_offer_exists(context):
            if prompt_support.is_generic_transition_reply(message_text):
                return prompt_support.build_progression_fallback_reply(context, user_message_text)
        return {"speaker_name": speaker_name, "message_text": message_text}
    except Exception:
        return prompt_support.fallback_reply(context, user_message_text)


def generate_line_visual_note(text_ai_client, context: dict, speaker_name: str, message_text: str) -> dict:
    prompt = prompt_support.build_line_visual_note_prompt(context, speaker_name, message_text)
    try:
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("line visual note response is invalid")
        parsed.setdefault("location", (context["state"].get("state_json") or {}).get("location"))
        parsed.setdefault("background", (context["state"].get("state_json") or {}).get("background"))
        parsed.setdefault("expression", (context["state"].get("state_json") or {}).get("expression") or "neutral")
        parsed.setdefault("pose", (context["state"].get("state_json") or {}).get("pose") or "conversation")
        parsed.setdefault("camera", (context["state"].get("state_json") or {}).get("camera") or "medium shot")
        parsed.setdefault("focus_object", None)
        parsed.setdefault("scene_moment", message_text[:120])
        return parsed
    except Exception:
        return prompt_support.fallback_line_visual_note(context, speaker_name, message_text)


def generate_conversation_evaluation(text_ai_client, context: dict) -> dict | None:
    if not prompt_support.get_session_objective(context):
        return None
    prompt = prompt_support.build_conversation_evaluation_prompt(context)
    try:
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("conversation evaluation response is invalid")
        score = int(parsed.get("score"))
        parsed["score"] = max(0, min(100, score))
        parsed["label"] = str(parsed.get("label") or "Progress").strip() or "Progress"
        parsed["reason"] = str(parsed.get("reason") or "").strip()
        parsed["mood"] = str(parsed.get("mood") or "").strip()
        theme = str(parsed.get("theme") or "general").strip().lower()
        parsed["theme"] = "romance" if theme == "romance" else "general"
        return parsed
    except Exception:
        return prompt_support.fallback_conversation_evaluation(context)


def generate_conversation_director(text_ai_client, context: dict, user_message_text: str) -> dict:
    prompt = prompt_support.build_conversation_director_prompt(context, user_message_text)
    try:
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("conversation director response is invalid")
        parsed.setdefault("turn_intent", "invite")
        parsed.setdefault("emotional_tone", "engaging")
        parsed.setdefault("relationship_goal", "build engagement")
        parsed.setdefault("scene_goal", "continue the conversation")
        parsed["must_include"] = [str(item).strip() for item in (parsed.get("must_include") or []) if str(item).strip()]
        parsed["avoid"] = [str(item).strip() for item in (parsed.get("avoid") or []) if str(item).strip()]
        return parsed
    except Exception:
        return prompt_support.fallback_conversation_director(context, user_message_text)


def generate_scene_progression(text_ai_client, context: dict, user_message_text: str) -> dict:
    prompt = prompt_support.build_scene_progression_prompt(context, user_message_text)
    try:
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.4,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("scene progression response is invalid")
        parsed.setdefault("scene_phase", "conversation")
        parsed.setdefault(
            "location",
            context["state"].get("state_json", {}).get("location")
            if isinstance(context["state"].get("state_json"), dict)
            else None,
        )
        parsed.setdefault("background", None)
        parsed.setdefault("focus_summary", "ongoing conversation")
        parsed.setdefault("next_topic", "continue the conversation")
        parsed["transition_occurred"] = bool(parsed.get("transition_occurred"))
        return parsed
    except Exception:
        return prompt_support.fallback_scene_progression(context, user_message_text)
