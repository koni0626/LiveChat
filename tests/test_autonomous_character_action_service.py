import json

from app.extensions import db
from app.models import Character, FeedPost, Project, User, WorldNewsItem
from app.services.autonomous_character_action_service import AutonomousCharacterActionService


def test_generate_actions_creates_feed_and_news_without_ai(app):
    with app.app_context():
        user = User(email="owner@example.com", display_name="owner", player_name="owner", status="active", role="project_user")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        project = Project(
            owner_user_id=user.id,
            title="Laplace City",
            genre="sci-fi",
            summary="A small city where characters leave traces.",
            status="active",
            visibility="private",
        )
        db.session.add(project)
        db.session.commit()

        character = Character(
            project_id=project.id,
            name="ノア",
            personality="穏やかで観測好き",
            speech_style="やわらかい",
        )
        db.session.add(character)
        db.session.commit()

        result = AutonomousCharacterActionService().generate_actions(
            project_id=project.id,
            count=1,
            target="both",
            use_ai=False,
        )

        assert result["count"] == 1
        assert result["items"][0]["feed_post_id"]
        assert result["items"][0]["news_id"]

        post = FeedPost.query.one()
        news = WorldNewsItem.query.one()
        assert post.project_id == project.id
        assert post.character_id == character.id
        assert post.status == "published"
        assert news.project_id == project.id
        assert news.related_character_id == character.id
        assert news.source_type == "autonomous_character_action"


def test_preview_actions_does_not_save_without_ai(app):
    with app.app_context():
        user = User(email="owner@example.com", display_name="owner", player_name="owner", status="active", role="project_user")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        project = Project(
            owner_user_id=user.id,
            title="Laplace City",
            genre="sci-fi",
            summary="A small city where characters leave traces.",
            status="active",
            visibility="private",
        )
        db.session.add(project)
        db.session.commit()

        db.session.add(Character(project_id=project.id, name="ノア"))
        db.session.commit()

        result = AutonomousCharacterActionService().preview_actions(
            project_id=project.id,
            count=2,
            use_ai=False,
        )

        assert result["count"] == 2
        assert FeedPost.query.count() == 0
        assert WorldNewsItem.query.count() == 0


def test_generate_actions_can_attach_romcom_feed_image_without_ai(app):
    class FakeFeedService:
        def __init__(self):
            self.calls = []

        def generate_post_image(self, post_id, payload):
            self.calls.append((post_id, payload))
            return type("UpdatedPost", (), {"image_asset_id": 123})()

    with app.app_context():
        user = User(email="owner-image@example.com", display_name="owner", player_name="owner", status="active", role="project_user")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        project = Project(
            owner_user_id=user.id,
            title="Romcom City",
            genre="romcom",
            summary="A city where emotional sightings become posts.",
            status="active",
            visibility="private",
        )
        db.session.add(project)
        db.session.commit()

        db.session.add(
            Character(
                project_id=project.id,
                name="Mika",
                personality="Easily flustered but tries to stay composed.",
                appearance_summary="Long red hair, gothic-inspired school outfit.",
            )
        )
        db.session.commit()

        fake_feed_service = FakeFeedService()
        result = AutonomousCharacterActionService(feed_service=fake_feed_service).generate_actions(
            project_id=project.id,
            count=1,
            target="feed",
            use_ai=False,
            with_images=True,
            image_size="1024x1024",
            image_quality="high",
        )

        assert result["items"][0]["image_asset_id"] == 123
        assert result["items"][0]["image_error"] is None
        assert len(fake_feed_service.calls) == 1
        post_id, payload = fake_feed_service.calls[0]
        assert post_id == result["items"][0]["feed_post_id"]
        assert payload["size"] == "1024x1024"
        assert payload["quality"] == "high"
        assert "romantic-comedy" in payload["prompt"]
        assert "No text, no captions" in payload["prompt"]


def test_generate_actions_without_ai_diversifies_characters_and_bodies(app):
    with app.app_context():
        user = User(email="owner-diverse@example.com", display_name="owner", player_name="owner", status="active", role="project_user")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        project = Project(
            owner_user_id=user.id,
            title="Diverse City",
            genre="romcom",
            summary="Characters should not all do the same thing.",
            status="active",
            visibility="private",
        )
        db.session.add(project)
        db.session.commit()

        for name in ("Mika", "Aoi", "Rin"):
            db.session.add(Character(project_id=project.id, name=name))
        db.session.commit()

        result = AutonomousCharacterActionService().generate_actions(
            project_id=project.id,
            count=3,
            target="feed",
            use_ai=False,
        )

        character_ids = [item["character_id"] for item in result["items"]]
        bodies = [item["feed_body"] for item in result["items"]]
        assert len(set(character_ids)) == 3
        assert len(set(bodies)) == 3


def test_generate_actions_rebalances_duplicate_ai_character_ids(app):
    class DuplicateCharacterTextAI:
        def generate_text(self, *_args, **_kwargs):
            return {
                "text": json.dumps(
                    {
                        "items": [
                            {
                                "character_id": 0,
                                "feed_body": "同じキャラの投稿その1",
                                "news_title": "同じキャラの噂その1",
                                "news_body": "同じキャラの本文その1",
                                "summary": "同じキャラの要約その1",
                            },
                            {
                                "character_id": 0,
                                "feed_body": "同じキャラの投稿その2",
                                "news_title": "同じキャラの噂その2",
                                "news_body": "同じキャラの本文その2",
                                "summary": "同じキャラの要約その2",
                            },
                        ]
                    }
                )
            }

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        user = User(email="owner-ai-diverse@example.com", display_name="owner", player_name="owner", status="active", role="project_user")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        project = Project(
            owner_user_id=user.id,
            title="AI Diverse City",
            genre="romcom",
            summary="AI may repeat ids, service should rebalance.",
            status="active",
            visibility="private",
        )
        db.session.add(project)
        db.session.commit()

        for name in ("Mika", "Aoi"):
            db.session.add(Character(project_id=project.id, name=name))
        db.session.commit()

        result = AutonomousCharacterActionService(text_ai_client=DuplicateCharacterTextAI()).generate_actions(
            project_id=project.id,
            count=2,
            target="feed",
        )

        character_ids = [item["character_id"] for item in result["items"]]
        assert len(set(character_ids)) == 2


def test_generate_actions_prompt_uses_feed_like_action_plans(app):
    class CaptureTextAI:
        def __init__(self):
            self.prompt = ""

        def generate_text(self, prompt, *_args, **_kwargs):
            self.prompt = prompt
            return {
                "text": json.dumps(
                    {
                        "items": [
                            {
                                "character_id": 0,
                                "feed_body": "計画に沿った投稿です。",
                                "news_title": "計画に沿った噂",
                                "news_body": "計画に沿った噂の本文です。",
                                "summary": "計画に沿った要約",
                                "image_mood": "surprised",
                                "visual_hook": "visible prop",
                            }
                        ]
                    }
                )
            }

        def _try_parse_json(self, text):
            return json.loads(text)

    with app.app_context():
        user = User(email="owner-plan@example.com", display_name="owner", player_name="owner", status="active", role="project_user")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        project = Project(
            owner_user_id=user.id,
            title="Plan City",
            genre="romcom",
            summary="Plans should guide autonomous posts.",
            status="active",
            visibility="private",
        )
        db.session.add(project)
        db.session.commit()

        db.session.add(Character(project_id=project.id, name="Mika"))
        db.session.add(Character(project_id=project.id, name="Aoi"))
        db.session.commit()

        text_ai = CaptureTextAI()
        AutonomousCharacterActionService(text_ai_client=text_ai).generate_actions(
            project_id=project.id,
            count=1,
            target="feed",
        )

        assert "今回のaction_plan" in text_ai.prompt
        assert "post_pattern" in text_ai.prompt
        assert "共演候補キャラクター" in text_ai.prompt
        assert "事件、目撃、引用、投票" in text_ai.prompt


def test_generate_actions_avoids_recent_autonomous_characters_without_ai(app):
    with app.app_context():
        user = User(email="owner-recent@example.com", display_name="owner", player_name="owner", status="active", role="project_user")
        user.set_password("password")
        db.session.add(user)
        db.session.commit()

        project = Project(
            owner_user_id=user.id,
            title="Recent City",
            genre="romcom",
            summary="Recent autonomous posts should be avoided.",
            status="active",
            visibility="private",
        )
        db.session.add(project)
        db.session.commit()

        characters = []
        for name in ("Mika", "Aoi", "Rin", "Yui"):
            character = Character(project_id=project.id, name=name)
            db.session.add(character)
            characters.append(character)
        db.session.commit()

        for character in characters[:2]:
            db.session.add(
                FeedPost(
                    project_id=project.id,
                    character_id=character.id,
                    created_by_user_id=user.id,
                    body=f"{character.name}の直近ログ",
                    status="published",
                    generation_state_json=json.dumps(
                        {
                            "source": "autonomous_character_action",
                            "action_type": "recent repeated beat",
                            "raw_item": {"summary": "recent"},
                        }
                    ),
                )
            )
        db.session.commit()

        result = AutonomousCharacterActionService().generate_actions(
            project_id=project.id,
            count=2,
            target="feed",
            use_ai=False,
        )

        selected_ids = {item["character_id"] for item in result["items"]}
        recent_ids = {character.id for character in characters[:2]}
        assert selected_ids.isdisjoint(recent_ids)
