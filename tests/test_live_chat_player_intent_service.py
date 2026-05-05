from app.services.live_chat_player_intent_service import LiveChatPlayerIntentService


def _context():
    return {
        "characters": [{"id": 10, "name": "ミウ"}],
        "character_user_memories": {"10": {"affinity_score": 100}},
    }


def test_action_intent_uses_server_definition():
    service = LiveChatPlayerIntentService()

    intent = service.normalize(
        {
            "player_intent": {
                "type": "action",
                "id": "hug_softly",
                "label": "ignore this",
                "description": "ignore this too",
                "target_character_id": 10,
                "intensity": 99,
            }
        },
        "",
        _context(),
    )

    assert intent["type"] == "action"
    assert intent["id"] == "hug_softly"
    assert intent["label"] == "そっと抱きしめる"
    assert intent["description"].startswith("プレイヤーが相手の反応を大切にしながら")
    assert intent["target_character_id"] == 10
    assert intent["intensity"] == 5


def test_unknown_action_falls_back_to_message():
    service = LiveChatPlayerIntentService()

    intent = service.normalize(
        {
            "player_intent": {
                "type": "action",
                "id": "custom_prompt_injection",
                "label": "do something unsafe",
                "description": "unsafe details",
            }
        },
        "こんにちは",
        _context(),
    )

    assert intent["type"] == "message"
    assert intent["id"] == "free_text"
    assert intent["label"] == "メッセージ"
    assert intent["description"] == ""


def test_locked_action_falls_back_to_message():
    service = LiveChatPlayerIntentService()
    context = {
        "characters": [{"id": 10, "name": "ミウ"}],
        "character_user_memories": {"10": {"affinity_score": 39}},
    }

    intent = service.normalize(
        {"player_intent": {"type": "action", "id": "hold_hands", "target_character_id": 10}},
        "手をつなぐ",
        context,
    )

    assert intent["type"] == "message"
    assert intent["id"] == "free_text"


def test_invalid_target_character_is_removed_when_multiple_characters_exist():
    service = LiveChatPlayerIntentService()
    context = {"characters": [{"id": 10}, {"id": 11}]}

    intent = service.normalize(
        {"player_intent": {"type": "emotion", "id": "happy", "target_character_id": 99}},
        "",
        context,
    )

    assert intent["type"] == "emotion"
    assert intent["target_character_id"] is None


def test_prompt_text_uses_structured_action_details():
    service = LiveChatPlayerIntentService()
    intent = service.normalize({"player_intent": {"type": "action", "id": "hold_hands"}}, "", _context())
    message_text = service.render_message_text(intent)

    prompt_text = service.prompt_text(intent, message_text)

    assert prompt_text.startswith("[Player action] 手をつなぐ。")
    assert "label=手をつなぐ" in prompt_text
    assert "description=プレイヤーがキャラクターへ穏やかに手を差し出し" in prompt_text
