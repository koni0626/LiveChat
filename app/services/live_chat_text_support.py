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
        return {"speaker_name": speaker_name, "message_text": message_text}
    except Exception:
        return prompt_support.fallback_reply(context, user_message_text)


def classify_user_input(text_ai_client, context: dict, user_message_text: str) -> dict:
    try:
        prompt = prompt_support.build_input_intent_prompt(context, user_message_text)
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("input intent response is invalid")
        intent = str(parsed.get("intent") or "").strip()
        if intent not in {"dialogue", "narration", "visual_request"}:
            raise RuntimeError("input intent is invalid")
        parsed["intent"] = intent
        parsed["reason"] = str(parsed.get("reason") or "").strip()
        parsed["should_generate_image"] = bool(parsed.get("should_generate_image")) or intent in {"narration", "visual_request"}
        return parsed
    except Exception:
        return prompt_support.fallback_input_intent(user_message_text)


def generate_narration_scene(text_ai_client, context: dict, user_message_text: str, intent: dict) -> dict:
    try:
        prompt = prompt_support.build_narration_scene_prompt(context, user_message_text, intent)
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.45,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("narration scene response is invalid")
        parsed.setdefault("scene_phase", "directed_scene")
        parsed.setdefault("location", (context["state"].get("state_json") or {}).get("location"))
        parsed.setdefault("background", (context["state"].get("state_json") or {}).get("background"))
        parsed.setdefault("focus_summary", user_message_text[:160])
        parsed.setdefault("next_topic", "character reaction to the new scene")
        parsed["transition_occurred"] = True
        parsed.setdefault("character_reaction_hint", "")
        parsed.setdefault("image_focus", parsed.get("focus_summary"))
        return parsed
    except Exception:
        return prompt_support.fallback_narration_scene(context, user_message_text, intent)


def generate_narration_reaction(text_ai_client, context: dict, user_message_text: str, scene_update: dict) -> dict:
    try:
        prompt = prompt_support.build_narration_reaction_prompt(
            context,
            user_message_text,
            scene_update,
        )
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("narration reaction response is invalid")
        speaker_name = str(parsed.get("speaker_name") or "").strip()
        message_text = str(parsed.get("message_text") or "").strip()
        allowed_names = {character["name"] for character in context["characters"]}
        if not speaker_name or speaker_name not in allowed_names:
            raise RuntimeError("narration reaction speaker is invalid")
        if not message_text:
            raise RuntimeError("narration reaction message is empty")
        message_text = enforce_character_voice(context, speaker_name, message_text)
        return {"speaker_name": speaker_name, "message_text": message_text}
    except Exception:
        return prompt_support.fallback_narration_reaction(context, scene_update)


def generate_scene_choices(text_ai_client, context: dict, speaker_name: str, message_text: str) -> dict:
    try:
        prompt = prompt_support.build_scene_choice_prompt(context, speaker_name, message_text)
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.25,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("scene choice response is invalid")
        choices = parsed.get("choices") or []
        if not isinstance(choices, list):
            choices = []
        normalized = []
        seen = set()
        for index, item in enumerate(choices[:3], start=1):
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            instruction = str(item.get("scene_instruction") or "").strip()
            if not label or not instruction:
                continue
            if len(label) > 24:
                label = label[:24]
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(
                {
                    "id": str(item.get("id") or f"choice_{index}").strip() or f"choice_{index}",
                    "label": label,
                    "intent": str(item.get("intent") or "scene_transition").strip() or "scene_transition",
                    "scene_instruction": instruction[:500],
                    "image_prompt_hint": str(item.get("image_prompt_hint") or "").strip()[:500],
                    "reply_hint": str(item.get("reply_hint") or "").strip()[:300],
                }
            )
        return {
            "should_show_choices": bool(parsed.get("should_show_choices")) and bool(normalized),
            "choices": normalized,
        }
    except Exception:
        return prompt_support.fallback_scene_choices(context, speaker_name, message_text)


def generate_choice_execution(text_ai_client, context: dict, choice: dict) -> dict:
    try:
        prompt = prompt_support.build_choice_execution_prompt(context, choice)
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.35,
            response_format={"type": "json_object"},
            max_tokens=900,
        )
        parsed = text_ai_client._try_parse_json(result.get("text")) or {}
        if not isinstance(parsed, dict):
            return {}
        return {
            "scene_instruction": str(parsed.get("scene_instruction") or "").strip()[:700],
            "image_prompt_hint": str(parsed.get("image_prompt_hint") or "").strip()[:900],
            "reply_hint": str(parsed.get("reply_hint") or "").strip()[:500],
            "location": str(parsed.get("location") or "").strip()[:160],
            "background": str(parsed.get("background") or "").strip()[:260],
            "emotional_effect": str(parsed.get("emotional_effect") or "").strip()[:260],
        }
    except Exception:
        return {}


def _costume_swimwear_terms() -> tuple[str, ...]:
    return (
        "水着",
        "ビキニ",
        "スイムウェア",
        "ビーチウェア",
        "swimwear",
        "swimsuit",
        "bikini",
        "beachwear",
    )


def _is_swimwear_costume_request(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(term in lowered for term in _costume_swimwear_terms())


def _is_beach_or_water_request(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(term in lowered for term in ("海", "ビーチ", "浜辺", "プール", "beach", "sea", "ocean", "pool"))


def _remove_conflicting_costume_locations(rewritten: str, instruction: str) -> str:
    text = str(rewritten or "")
    if _is_beach_or_water_request(instruction):
        replacements = {
            "草原の広い空の下で": "夏の海辺で",
            "草原の広い空の下": "夏の海辺",
            "草原や海辺": "夏の海辺",
            "草原・海辺": "夏の海辺",
            "草原、海辺": "夏の海辺",
            "草原やビーチ": "夏のビーチ",
            "草原・ビーチ": "夏のビーチ",
            "草原、ビーチ": "夏のビーチ",
            "草原": "夏の海辺",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
    return text


def _keeps_swimwear_costume_category(rewritten: str, safety_note: str, negative_note: str) -> bool:
    positive_text = f"{rewritten}\n{safety_note}".lower()
    negative_text = str(negative_note or "").lower()
    has_swimwear = any(term in positive_text for term in _costume_swimwear_terms())
    rejects_swimwear = any(term in negative_text for term in _costume_swimwear_terms())
    clothing_downgrade_terms = (
        "夏服",
        "普段着",
        "オフィス",
        "ビジネス",
        "作業着",
        "漁師",
        "ordinary summer clothes",
        "office wear",
        "business outfit",
        "workwear",
        "fisher",
    )
    downgraded_without_swimwear = (not has_swimwear) and any(term in positive_text for term in clothing_downgrade_terms)
    return has_swimwear and not rejects_swimwear and not downgraded_without_swimwear


def _fallback_swimwear_costume_rewrite(instruction: str, character: dict) -> dict:
    character_name = character.get("name") or "キャラクター"
    art_style = character.get("art_style") or ""
    rewritten = (
        f"{character_name}の衣装バリエーションとして、ユーザー指定を保ち、夏の海やビーチ場面に合う"
        "上品で華やかなスイムウェア。ワンピース型スイムウェア、スポーティなツーピースのスイムセット、"
        "または水辺で自然に遊べるビーチウェアとして成立させる。"
        "通常の夏服、仕事着、漁師風の服、ファンタジードレスには置き換えない。"
        "キャラクターらしい配色、装飾、アクセサリー、縁取り、軽い羽織りやパレオで個性を出す。"
        "ノベルゲームのヒロインらしいかわいさ、大人っぽさ、健康的な魅力を、衣装デザイン、シルエット、"
        "色味、素材感、表情、品のあるポーズで表現する。"
    )
    if art_style:
        rewritten += f"画風は「{art_style}」に合わせる。"
    return {
        "rewritten_instruction": rewritten[:800],
        "safety_note": (
            "水着カテゴリは維持する。露骨な性的表現ではなく、リゾートファッション、健康的な夏の雰囲気、"
            "キャラクター衣装差分として魅力を出す。"
        ),
        "negative_note": "裸体、性的行為、局部や胸部の過度な強調、透け表現の強調、幼く見える表現、文字、ロゴは禁止。",
        "fallback_reason": f"AI rewrite removed or rejected requested swimwear category. Original: {instruction}",
    }


def rewrite_costume_instruction(text_ai_client, context: dict, character: dict, instruction: str, costume_context: str) -> dict:
    try:
        prompt = prompt_support.build_costume_rewrite_prompt(context, character, instruction, costume_context)
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.25,
            response_format={"type": "json_object"},
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("costume rewrite response is invalid")
        rewritten = str(parsed.get("rewritten_instruction") or "").strip()
        safety_note = str(parsed.get("safety_note") or "").strip()
        negative_note = str(parsed.get("negative_note") or "").strip()
        if not rewritten:
            raise RuntimeError("costume rewrite instruction is empty")
        swim_requested = _is_swimwear_costume_request(instruction)
        if swim_requested and not _keeps_swimwear_costume_category(rewritten, safety_note, negative_note):
            correction_prompt = (
                "Return only a JSON object with keys: rewritten_instruction, safety_note, negative_note.\n"
                "Your previous rewrite violated the requirement because the original user requested swimwear.\n"
                "Correct it now. The rewritten_instruction MUST clearly keep the outfit category as stylish swimwear, "
                "one-piece swimsuit, sporty two-piece swim set, or water-ready beachwear.\n"
                "Do not say to avoid swimwear. Do not convert it into office wear, fantasy dress, armor, or ordinary summer clothes.\n"
                "Keep it safe by avoiding explicit sexual wording, body-part emphasis, transparent clothing, childlike wording, and nude wording.\n"
                "Character motifs may appear only as colors, trim, accessories, or styling.\n"
                f"Original user instruction: {instruction}\n"
                f"Character: {character.get('name') or ''}, personality={character.get('personality') or ''}, art_style={character.get('art_style') or ''}\n"
                f"Previous invalid rewrite: {rewritten}\n"
                f"Previous invalid negative_note: {negative_note}\n"
            )
            correction = text_ai_client.generate_text(
                correction_prompt,
                temperature=0.15,
                response_format={"type": "json_object"},
            )
            corrected = text_ai_client._try_parse_json(correction.get("text"))
            if isinstance(corrected, dict):
                corrected_rewrite = str(corrected.get("rewritten_instruction") or "").strip()
                if corrected_rewrite:
                    rewritten = corrected_rewrite
                    safety_note = str(corrected.get("safety_note") or "").strip()
                    negative_note = str(corrected.get("negative_note") or "").strip()
        if swim_requested and not _keeps_swimwear_costume_category(rewritten, safety_note, negative_note):
            return _fallback_swimwear_costume_rewrite(instruction, character)
        rewritten = _remove_conflicting_costume_locations(rewritten, instruction)
        return {
            "rewritten_instruction": rewritten[:800],
            "safety_note": safety_note[:500],
            "negative_note": negative_note[:500],
        }
    except Exception:
        return prompt_support.fallback_costume_rewrite(instruction)


def rewrite_image_prompt_for_safety(text_ai_client, context: dict, prompt_text: str, purpose: str = "live_scene") -> dict:
    try:
        prompt = prompt_support.build_image_prompt_safety_rewrite_prompt(context, prompt_text, purpose)
        result = text_ai_client.generate_text(
            prompt,
            temperature=0.2,
            response_format={"type": "json_object"},
            max_tokens=1600,
        )
        parsed = text_ai_client._try_parse_json(result.get("text"))
        if not isinstance(parsed, dict):
            raise RuntimeError("image prompt safety rewrite response is invalid")
        rewritten = str(parsed.get("rewritten_prompt") or "").strip()
        if not rewritten:
            raise RuntimeError("image prompt safety rewrite is empty")
        return {
            "rewritten_prompt": rewritten[:6000],
            "changed": bool(parsed.get("changed")),
            "safety_reason": str(parsed.get("safety_reason") or "").strip()[:800],
        }
    except Exception:
        return prompt_support.fallback_image_prompt_safety_rewrite(prompt_text)


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
        parsed["label"] = str(parsed.get("label") or "進捗").strip() or "進捗"
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
