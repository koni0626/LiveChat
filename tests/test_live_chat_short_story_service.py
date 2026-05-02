import json

import pytest

from app.services.live_chat_short_story_service import LiveChatShortStoryService


class _FakeTextAIClient:
    def __init__(self):
        self.prompt = None

    def generate_text(self, prompt, **_kwargs):
        self.prompt = prompt
        return {
            "model": "fake-model",
            "text": json.dumps(
                {
                    "title": "雨上がりの約束",
                    "synopsis": "会話の余韻から生まれた短い約束の物語。",
                    "body": "雨上がりの街で、二人はさっきの言葉を思い返していた。",
                    "afterword": "直近の会話にあった誘いと照れを拾っています。",
                },
                ensure_ascii=False,
            ),
        }

    def _try_parse_json(self, text):
        return json.loads(text)


class _FakeSession:
    id = 1
    settings_json = None


class _FakeChatSessionService:
    def __init__(self):
        self.session = _FakeSession()
        self.updated_payload = None

    def get_session(self, _session_id):
        return self.session

    def update_session(self, _session_id, payload):
        self.updated_payload = payload
        self.session.settings_json = payload.get("settings_json")
        return self.session


def _context():
    return {
        "project": {"title": "Test Project"},
        "world": {"name": "水都", "overview": "雨と運河の街"},
        "session": {"title": "夜の散歩", "player_name": "ミナト", "settings_json": {}},
        "room": {"conversation_objective": "二人で街を歩く約束をする"},
        "characters": [
            {
                "name": "凛",
                "personality": "素直ではないが面倒見がいい",
                "speech_style": "短く照れ隠しをする",
                "first_person": "私",
                "second_person": "あなた",
            }
        ],
        "messages": [
            {"sender_type": "user", "speaker_name": None, "message_text": "少し歩かない？"},
            {"sender_type": "character", "speaker_name": "凛", "message_text": "別に、嫌じゃないけど。"},
        ],
    }


def test_generate_short_story_uses_chat_log():
    client = _FakeTextAIClient()
    service = LiveChatShortStoryService(text_ai_client=client, context_provider=lambda _session_id: _context())

    story = service.generate_short_story(1)

    assert story["title"] == "雨上がりの約束"
    assert story["source_message_count"] == 2
    assert story["model"] == "fake-model"
    assert "少し歩かない？" in client.prompt
    assert "凛" in client.prompt


def test_generate_short_story_uses_style_instruction():
    client = _FakeTextAIClient()
    service = LiveChatShortStoryService(text_ai_client=client, context_provider=lambda _session_id: _context())

    service.generate_short_story(
        1,
        {
            "tone": "会話のテンポがよいギャグ短編",
            "length": "800〜1200字",
            "instruction": "最後はしっとり終える",
        },
    )

    assert "文体: 会話のテンポがよいギャグ短編" in client.prompt
    assert "本文の長さ: 800〜1200字" in client.prompt
    assert "追加指示: 最後はしっとり終える" in client.prompt


def test_generate_short_story_can_attach_images(monkeypatch):
    client = _FakeTextAIClient()
    service = LiveChatShortStoryService(text_ai_client=client, context_provider=lambda _session_id: _context())
    monkeypatch.setattr(
        service,
        "_generate_story_images",
        lambda *_args, **_kwargs: {
            "opening": {"id": 10, "asset": {"media_url": "/media/opening.png"}},
            "ending": {"id": 11, "asset": {"media_url": "/media/ending.png"}},
        },
    )

    story = service.generate_short_story(1, {"generate_images": True})

    assert story["images"]["opening"]["asset"]["media_url"] == "/media/opening.png"
    assert story["images"]["ending"]["asset"]["media_url"] == "/media/ending.png"


def test_save_short_story_persists_to_session_settings():
    chat_session_service = _FakeChatSessionService()
    service = LiveChatShortStoryService(
        text_ai_client=_FakeTextAIClient(),
        context_provider=lambda _session_id: _context(),
        chat_session_service=chat_session_service,
    )

    result = service.save_short_story(
        1,
        {
            "story": {
                "title": "雨上がりの約束",
                "synopsis": "短い約束の話。",
                "body": "本文です。",
                "afterword": "ログを拾っています。",
                "source_message_count": 2,
                "images": {"opening": {"id": 10}, "ending": {"id": 11}},
            }
        },
    )

    assert result["saved_count"] == 1
    saved = chat_session_service.updated_payload["settings_json"]["saved_short_stories"][0]
    assert saved["title"] == "雨上がりの約束"
    assert saved["images"]["opening"]["id"] == 10


def test_generate_short_story_requires_enough_messages():
    context = _context()
    context["messages"] = [{"sender_type": "user", "message_text": "こんにちは"}]
    service = LiveChatShortStoryService(text_ai_client=_FakeTextAIClient(), context_provider=lambda _session_id: context)

    with pytest.raises(ValueError):
        service.generate_short_story(1)
