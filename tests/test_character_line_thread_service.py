import json
from io import BytesIO

from PIL import Image
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import Asset, Character, CharacterLineMessage, CharacterLineRoom, CharacterMemoryNote, Project, User, WorldLocation
from app.services.character_line_thread_service import CharacterLineThreadService


def _create_project_with_characters(names):
    user = User(email="line-owner@example.com", display_name="owner", player_name="owner", status="active", role="project_user")
    user.set_password("password")
    db.session.add(user)
    db.session.commit()

    project = Project(
        owner_user_id=user.id,
        title="Line City",
        genre="romcom",
        summary="Characters react loudly to player topics.",
        status="active",
        visibility="private",
    )
    db.session.add(project)
    db.session.commit()

    for name in names:
        db.session.add(
            Character(
                project_id=project.id,
                name=name,
                personality=f"{name} personality",
                speech_style=f"{name} style",
            )
        )
    db.session.commit()
    return project


def _image_upload(filename="line.png"):
    buffer = BytesIO()
    Image.new("RGB", (12, 12), color=(200, 40, 80)).save(buffer, format="PNG")
    buffer.seek(0)
    return FileStorage(stream=buffer, filename=filename, content_type="image/png")


def test_generate_line_thread_without_ai_returns_text_messages(app):
    with app.app_context():
        project = _create_project_with_characters(["ノア", "ミカ", "アオイ"])

        result = CharacterLineThreadService().generate_thread(
            project_id=project.id,
            theme="ノアの露出度について",
            turns=8,
            participant_count=3,
            use_ai=False,
        )

        assert result["theme"] == "ノアの露出度について"
        assert len(result["messages"]) == 8
        assert len(result["participant_ids"]) == 3
        assert result["punchline"]

        text = CharacterLineThreadService().format_thread_text(result)
        assert "theme: ノアの露出度について" in text
        assert "01." in text


def test_generate_line_thread_prompt_contains_manager_plan(app):
    class CaptureTextAI:
        def __init__(self):
            self.prompt = ""

        def generate_text(self, prompt, *_args, **_kwargs):
            self.prompt = prompt
            return {
                "text": json.dumps(
                    {
                        "title": "ノア会議",
                        "theme": "ノアの露出度について",
                        "punchline": "グループ名が先に変わった。",
                        "messages": [
                            {"turn": 1, "speaker_id": 0, "speaker_name": "?", "text": "まず議題名が強い。"},
                            {"turn": 2, "speaker_id": 0, "speaker_name": "?", "text": "本人の尊厳を戻そう。"},
                            {"turn": 3, "speaker_id": 0, "speaker_name": "?", "text": "結論、名前を変えよう。"},
                            {"turn": 4, "speaker_id": 0, "speaker_name": "?", "text": "変えたら通知が平和。"},
                        ],
                    }
                )
            }

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        project = _create_project_with_characters(["ノア", "ミカ", "アオイ"])
        text_ai = CaptureTextAI()

        result = CharacterLineThreadService(text_ai_client=text_ai).generate_thread(
            project_id=project.id,
            theme="ノアの露出度について",
            turns=4,
            participant_count=3,
        )

        assert result["title"] == "ノア会議"
        assert len(result["messages"]) == 4
        assert "Manager plan" in text_ai.prompt
        assert "Participants" in text_ai.prompt
        assert "Theme from player: ノアの露出度について" in text_ai.prompt
        assert "Comedy beat menu" in text_ai.prompt
        assert "boke/tsukkomi rhythm" in text_ai.prompt
        assert "ten-don" in text_ai.prompt
        assert "Story phases" in text_ai.prompt
        assert "natural back-and-forth" in text_ai.prompt
        assert "Do not force catchphrases" in text_ai.prompt
        assert "Current participant presence" in text_ai.prompt
        assert "all present in this LINE room" in text_ai.prompt
        assert "Do not say a current participant is absent" in text_ai.prompt


def test_generate_line_thread_uses_turns_as_max_by_default(app):
    class ShortTextAI:
        def __init__(self):
            self.prompt = ""

        def generate_text(self, prompt, *_args, **_kwargs):
            self.prompt = prompt
            return {
                "text": json.dumps(
                    {
                        "title": "短めLINE",
                        "theme": "ノアの露出度について",
                        "punchline": "短く落ちた。",
                        "messages": [
                            {"turn": 1, "speaker_id": 0, "speaker_name": "?", "text": "単語が強い。"},
                            {"turn": 2, "speaker_id": 0, "speaker_name": "?", "text": "本人に聞こう。"},
                            {"turn": 3, "speaker_id": 0, "speaker_name": "?", "text": "名前だけ変えよう。"},
                            {"turn": 4, "speaker_id": 0, "speaker_name": "?", "text": "それが一番平和。"},
                        ],
                    }
                )
            }

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        project = _create_project_with_characters(["ノア", "ミカ", "アオイ"])
        text_ai = ShortTextAI()

        result = CharacterLineThreadService(text_ai_client=text_ai).generate_thread(
            project_id=project.id,
            theme="ノアの露出度について",
            turns=20,
            participant_count=3,
        )

        assert len(result["messages"]) == 4
        assert "between 4 and 20 messages" in text_ai.prompt
        assert "do not pad to the maximum" in text_ai.prompt


def test_generate_line_thread_exact_turns_rejects_short_ai_and_falls_back(app):
    class ShortTextAI:
        def generate_text(self, *_args, **_kwargs):
            return {
                "text": json.dumps(
                    {
                        "messages": [
                            {"turn": 1, "speaker_id": 0, "speaker_name": "?", "text": "短い。"},
                            {"turn": 2, "speaker_id": 0, "speaker_name": "?", "text": "終わり。"},
                        ]
                    }
                )
            }

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        project = _create_project_with_characters(["ノア", "ミカ", "アオイ"])

        result = CharacterLineThreadService(text_ai_client=ShortTextAI()).generate_thread(
            project_id=project.id,
            theme="ノアの露出度について",
            turns=6,
            participant_count=3,
            exact_turns=True,
        )

        assert len(result["messages"]) == 6


def test_line_rooms_default_room_and_custom_room(app):
    with app.app_context():
        project = _create_project_with_characters(["Noa", "Mika", "Aoi"])
        user = User.query.filter_by(email="line-owner@example.com").first()
        characters = Character.query.filter_by(project_id=project.id).order_by(Character.id.asc()).all()
        service = CharacterLineThreadService()

        rooms = service.list_rooms(project_id=project.id, user_id=user.id)
        assert len(rooms) == 1
        assert rooms[0]["is_default"] is True
        assert rooms[0]["participant_count"] == 3

        custom = service.create_room(
            project_id=project.id,
            user_id=user.id,
            payload={"title": "放課後LINE", "participant_ids": [characters[0].id, characters[2].id]},
        )
        assert custom["title"] == "放課後LINE"
        assert custom["participant_ids"] == [characters[0].id, characters[2].id]
        assert custom["participant_count"] == 2


def test_generate_room_reply_persists_player_and_character_messages(app):
    with app.app_context():
        project = _create_project_with_characters(["Noa", "Mika", "Aoi"])
        user = User.query.filter_by(email="line-owner@example.com").first()
        room = CharacterLineRoom(project_id=project.id, created_by_user_id=user.id, title="Test LINE", is_default=True)
        db.session.add(room)
        db.session.commit()

        result = CharacterLineThreadService().generate_room_reply(
            room_id=room.id,
            user_id=user.id,
            body="ノアの露出度について",
            turns=5,
            use_ai=False,
        )

        assert result["player_message"]["sender_type"] == "player"
        assert result["messages"]
        assert all(message["sender_type"] == "character" for message in result["messages"])
        assert CharacterLineMessage.query.filter_by(room_id=room.id).count() == 1 + len(result["messages"])
        assert CharacterLineRoom.query.get(room.id).last_theme == "ノアの露出度について"


def test_generate_room_reply_passes_latest_40_room_messages_to_prompt(app):
    class CaptureTextAI:
        def __init__(self, speaker_id):
            self.prompt = ""
            self.prompts = []
            self.speaker_id = speaker_id

        def generate_text(self, prompt, *_args, **_kwargs):
            self.prompt = prompt
            self.prompts.append(prompt)
            return {
                "text": json.dumps(
                    {
                        "messages": [
                            {"turn": 1, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "history ok 1"},
                            {"turn": 2, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "history ok 2"},
                            {"turn": 3, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "history ok 3"},
                            {"turn": 4, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "history ok 4"},
                        ]
                    }
                )
            }

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        project = _create_project_with_characters(["Noa", "Mika", "Aoi"])
        user = User.query.filter_by(email="line-owner@example.com").first()
        character = Character.query.filter_by(project_id=project.id, name="Noa").first()
        room = CharacterLineRoom(project_id=project.id, created_by_user_id=user.id, title="Test LINE", is_default=True)
        db.session.add(room)
        db.session.commit()
        for index in range(1, 46):
            db.session.add(
                CharacterLineMessage(
                    room_id=room.id,
                    project_id=project.id,
                    sender_type="character" if index % 2 else "player",
                    character_id=character.id if index % 2 else None,
                    user_id=user.id if index % 2 == 0 else None,
                    body=f"old-{index:02d}",
                    turn_index=index,
                )
            )
        db.session.commit()
        text_ai = CaptureTextAI(character.id)

        CharacterLineThreadService(text_ai_client=text_ai).generate_room_reply(
            room_id=room.id,
            user_id=user.id,
            body="new-topic",
            turns=4,
        )

        line_prompt = next(prompt for prompt in text_ai.prompts if "Recent room history" in prompt)
        assert "old-06" in line_prompt
        assert "old-45" in line_prompt
        assert "old-05" not in line_prompt
        assert "Use Recent room history as short-term memory" in line_prompt


def test_generate_room_reply_extracts_character_line_memory_notes(app):
    class LineMemoryTextAI:
        def __init__(self, speaker_id):
            self.speaker_id = speaker_id

        def generate_text(self, prompt, *_args, **_kwargs):
            if "Extract durable character memory notes" in prompt:
                assert "Do not extract personality traits" in prompt
                assert "Each note must read like a past memory" in prompt
                return {
                    "text": json.dumps(
                        {
                            "notes": [
                                {
                                    "category": "relationship",
                                    "note": "以前LINEで、MikaがPonとNoaは仲良しだと茶化し、それが次に呼び戻せる内輪ネタになった。",
                                    "confidence": 0.9,
                                },
                                {
                                    "category": "habit",
                                    "note": "Noa has a habit of checking safety before jokes.",
                                    "confidence": 0.95,
                                }
                            ]
                        }
                    )
                }
            return {
                "text": json.dumps(
                    {
                        "messages": [
                            {"turn": 1, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "Pon and Noa are close."},
                            {"turn": 2, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "Mika made it a running joke."},
                            {"turn": 3, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "Everyone remembers it."},
                            {"turn": 4, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "Next time we call back to it."},
                        ]
                    }
                )
            }

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        project = _create_project_with_characters(["Noa", "Mika", "Aoi"])
        user = User.query.filter_by(email="line-owner@example.com").first()
        character = Character.query.filter_by(project_id=project.id, name="Noa").first()
        room = CharacterLineRoom(project_id=project.id, created_by_user_id=user.id, title="Test LINE", is_default=True)
        db.session.add(room)
        db.session.commit()

        result = CharacterLineThreadService(text_ai_client=LineMemoryTextAI(character.id)).generate_room_reply(
            room_id=room.id,
            user_id=user.id,
            body="remember this",
            turns=4,
        )

        assert result["created_memories"]
        notes = CharacterMemoryNote.query.filter_by(source_type="character_line_ai").all()
        assert len(notes) == 3
        assert all("以前LINEで" in note.note for note in notes)
        assert all("内輪ネタ" in note.note for note in notes)
        assert all(note.category == "relationship" for note in notes)
        assert all("habit" not in note.note for note in notes)


def test_generate_thread_prompt_includes_long_term_line_memories(app):
    class CaptureTextAI:
        def __init__(self, speaker_id):
            self.speaker_id = speaker_id
            self.prompts = []

        def generate_text(self, prompt, *_args, **_kwargs):
            self.prompts.append(prompt)
            return {
                "text": json.dumps(
                    {
                        "messages": [
                            {"turn": 1, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "memory used 1"},
                            {"turn": 2, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "memory used 2"},
                            {"turn": 3, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "memory used 3"},
                            {"turn": 4, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "memory used 4"},
                        ]
                    }
                )
            }

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        project = _create_project_with_characters(["Noa", "Mika", "Aoi"])
        user = User.query.filter_by(email="line-owner@example.com").first()
        character = Character.query.filter_by(project_id=project.id, name="Noa").first()
        db.session.add(
            CharacterMemoryNote(
                user_id=user.id,
                character_id=character.id,
                category="relationship",
                note="Noa remembers that Pon and Noa became close in a LINE room.",
                source_type="character_line_ai",
                confidence=0.9,
            )
        )
        room = CharacterLineRoom(project_id=project.id, created_by_user_id=user.id, title="Test LINE", is_default=True)
        db.session.add(room)
        db.session.commit()
        text_ai = CaptureTextAI(character.id)

        CharacterLineThreadService(text_ai_client=text_ai).generate_room_reply(
            room_id=room.id,
            user_id=user.id,
            body="use memory",
            turns=4,
        )

        line_prompt = next(prompt for prompt in text_ai.prompts if "Long-term participant memories" in prompt)
        assert "Noa remembers that Pon and Noa became close" in line_prompt
        assert "Use Long-term participant memories as durable memory" in line_prompt


def test_generate_thread_prompt_includes_light_world_location_index(app):
    class CaptureTextAI:
        def __init__(self, speaker_id):
            self.speaker_id = speaker_id
            self.prompts = []

        def generate_text(self, prompt, *_args, **_kwargs):
            self.prompts.append(prompt)
            return {
                "text": json.dumps(
                    {
                        "messages": [
                            {"turn": 1, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "location used 1"},
                            {"turn": 2, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "location used 2"},
                            {"turn": 3, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "location used 3"},
                            {"turn": 4, "speaker_id": self.speaker_id, "speaker_name": "Noa", "text": "location used 4"},
                        ]
                    }
                )
            }

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        project = _create_project_with_characters(["Noa", "Mika", "Aoi"])
        user = User.query.filter_by(email="line-owner@example.com").first()
        character = Character.query.filter_by(project_id=project.id, name="Noa").first()
        db.session.add(
            WorldLocation(
                project_id=project.id,
                name="駅前カフェ",
                region="中央区",
                location_type="カフェ",
                tags_json=json.dumps(["待ち合わせ", "甘いもの"]),
                description="駅前にある小さなカフェ。キャラクターが放課後に集まりやすく、軽い噂話が自然に起きる。",
                owner_character_id=character.id,
                status="published",
            )
        )
        room = CharacterLineRoom(project_id=project.id, created_by_user_id=user.id, title="Test LINE", is_default=True)
        db.session.add(room)
        db.session.commit()
        text_ai = CaptureTextAI(character.id)

        CharacterLineThreadService(text_ai_client=text_ai).generate_room_reply(
            room_id=room.id,
            user_id=user.id,
            body="どこで話す？",
            turns=4,
        )

        line_prompt = next(prompt for prompt in text_ai.prompts if "World location index" in prompt)
        assert "駅前カフェ" in line_prompt
        assert "owner_name" in line_prompt
        assert "Noa" in line_prompt
        assert "owner_is_participant" in line_prompt
        assert "Facility knowledge has gradients" in line_prompt
        assert "Do not force facilities into the chat" in line_prompt


def test_generate_room_reply_uploads_and_understands_photo(app, tmp_path):
    class VisionTextAI:
        def analyze_image(self, file_path, **_kwargs):
            assert file_path
            return {
                "parsed_json": {
                    "label": "赤い小物の写真",
                    "short_description": "赤い小物が中央に写っている写真。",
                    "visible_subjects": ["赤い小物"],
                    "mood": "少し目立つ",
                    "conversation_hooks": ["赤が強い", "誰の持ち物か気になる"],
                }
            }

        def generate_text(self, *_args, **_kwargs):
            raise AssertionError("generate_text should not be called with use_ai=False")

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        app.config["STORAGE_ROOT"] = str(tmp_path)
        app.config["ASSET_ALLOWED_IMAGE_MIME_TYPES"] = {"image/png", "image/jpeg", "image/webp", "image/gif"}
        project = _create_project_with_characters(["Noa", "Mika", "Aoi"])
        user = User.query.filter_by(email="line-owner@example.com").first()
        room = CharacterLineRoom(project_id=project.id, created_by_user_id=user.id, title="Photo LINE", is_default=True)
        db.session.add(room)
        db.session.commit()

        result = CharacterLineThreadService(text_ai_client=VisionTextAI()).generate_room_reply(
            room_id=room.id,
            user_id=user.id,
            body="これ見て",
            turns=4,
            use_ai=False,
            upload_file=_image_upload(),
        )

        player = result["player_message"]
        assert player["image_asset"]["asset_type"] == "character_line_upload_image"
        assert player["image_observation"]["label"] == "赤い小物の写真"
        assert "赤い小物が中央" in player["body"]
        assert Asset.query.filter_by(asset_type="character_line_upload_image").count() == 1
