from __future__ import annotations

from . import live_chat_prompt_text_support as text_prompt_support
from . import live_chat_prompt_visual_support as visual_prompt_support


def get_session_objective(context: dict) -> str | None:
    return text_prompt_support.get_session_objective(context)


def _active_characters(context: dict, state_json: dict) -> list[dict]:
    return visual_prompt_support.active_characters(context, state_json)


def build_opening_prompt(context: dict) -> str:
    return text_prompt_support.build_opening_prompt(context)


def fallback_opening_message(context: dict) -> dict:
    return text_prompt_support.fallback_opening_message(context)


def normalize_compare_text(text: str) -> str:
    return text_prompt_support.normalize_compare_text(text)


def is_affirmative_progress_message(text: str) -> bool:
    return text_prompt_support.is_affirmative_progress_message(text)


def recent_transition_offer_exists(context: dict) -> bool:
    return text_prompt_support.recent_transition_offer_exists(context)


def is_generic_transition_reply(text: str) -> bool:
    return text_prompt_support.is_generic_transition_reply(text)


def build_progression_fallback_reply(context: dict, user_message_text: str) -> dict:
    return text_prompt_support.build_progression_fallback_reply(context, user_message_text)


def build_reply_prompt(context: dict, user_message_text: str) -> str:
    return text_prompt_support.build_reply_prompt(context, user_message_text)


def fallback_reply(context: dict, user_message_text: str) -> dict:
    return text_prompt_support.fallback_reply(context, user_message_text)


def build_line_visual_note_prompt(context: dict, speaker_name: str, message_text: str) -> str:
    return text_prompt_support.build_line_visual_note_prompt(context, speaker_name, message_text)


def fallback_line_visual_note(context: dict, speaker_name: str, message_text: str) -> dict:
    return text_prompt_support.fallback_line_visual_note(context, speaker_name, message_text)


def build_session_memory(messages: list[dict], current_state_json: dict | None) -> dict:
    return text_prompt_support.build_session_memory(messages, current_state_json)


def build_conversation_evaluation_prompt(context: dict) -> str:
    return text_prompt_support.build_conversation_evaluation_prompt(context)


def fallback_conversation_evaluation(context: dict) -> dict:
    return text_prompt_support.fallback_conversation_evaluation(context)


def build_conversation_director_prompt(context: dict, user_message_text: str) -> str:
    return text_prompt_support.build_conversation_director_prompt(context, user_message_text)


def fallback_conversation_director(context: dict, user_message_text: str) -> dict:
    return text_prompt_support.fallback_conversation_director(context, user_message_text)


def apply_director_relationship_update(relationship_state: dict, context: dict, director: dict) -> dict:
    return text_prompt_support.apply_director_relationship_update(relationship_state, context, director)


def build_scene_progression_prompt(context: dict, user_message_text: str) -> str:
    return text_prompt_support.build_scene_progression_prompt(context, user_message_text)


def fallback_scene_progression(context: dict, user_message_text: str) -> dict:
    return text_prompt_support.fallback_scene_progression(context, user_message_text)


def build_recent_conversation_excerpt_ja(messages: list[dict], limit: int = 6) -> str:
    return visual_prompt_support.build_recent_conversation_excerpt_ja(messages, limit=limit)


def build_visual_state(context: dict, state: dict, *, prompt: str) -> dict:
    return visual_prompt_support.build_visual_state(context, state, prompt=prompt)


def build_japanese_conversation_image_prompt_request(context: dict, state: dict) -> str:
    return visual_prompt_support.build_japanese_conversation_image_prompt_request(context, state)


def fallback_japanese_conversation_image_prompt(context: dict, state: dict) -> dict:
    return visual_prompt_support.fallback_japanese_conversation_image_prompt(context, state)


def normalize_first_person_visual_prompt(prompt: str) -> str:
    return visual_prompt_support.normalize_first_person_visual_prompt(prompt)
