from datetime import datetime, timezone
from types import SimpleNamespace

from app.extensions import db
from app.models import User
from app.models.character import Character
from app.models.project import Project
from app.services.x_timeline_digest_service import XRecentPost, XTimelineDigestService


def _create_project_with_reply_characters():
    user = User(email="reply@example.com", display_name="Reply User", password_hash="x")
    db.session.add(user)
    db.session.flush()
    project = Project(owner_user_id=user.id, title="Laplace", genre="fantasy", project_type="linear")
    db.session.add(project)
    db.session.flush()
    db.session.add_all(
        [
            Character(
                project_id=project.id,
                name="ノア",
                nickname="ノア",
                personality="穏やかで相手をよく見る。",
                speech_style="やわらかく丁寧。",
                speech_sample="素敵ですね。少し見入ってしまいました。",
            ),
            Character(
                project_id=project.id,
                name="ドル",
                nickname="ラプラスシティの資産家",
                personality="商売上手。",
            ),
            Character(
                project_id=project.id,
                name="ラプラス",
                nickname="ラプ",
                personality="少し気まぐれで率直。",
                speech_style="短く、軽く茶目っ気がある。",
                speech_sample="いいね、それ。嫌いじゃないよ。",
            ),
        ]
    )
    db.session.commit()
    return project


class _ReplyTextAI:
    def generate_text(self, *_args, **_kwargs):
        return {
            "text": (
                '{"suggestions":['
                '{"character_id":1,"character":"ノア","text":"朝の空気がきれいですね。少し元気をもらいました。"},'
                '{"character_id":3,"character":"ラプラス","text":"いいね、この感じ。ちょっと好きかも。"}'
                "]}"
            )
        }


class _FailingTextAI:
    def generate_text(self, *_args, **_kwargs):
        raise RuntimeError("boom")


class _PartialTextAI:
    def generate_text(self, *_args, **_kwargs):
        return {"text": '{"suggestions":[{"character_id":1,"character":"ノア","text":"素敵な朝ですね。"}]}'}


class _SingleReplyTextAI:
    def generate_text(self, *_args, **_kwargs):
        return {"text": '{"comment":"光の入り方がやわらかくて素敵ですね。 #AIArt https://example.com"}'}


def test_reply_suggestions_render_as_manual_candidates(app):
    project = _create_project_with_reply_characters()
    post = XRecentPost(
        id="123",
        text="朝の写真です #AIArt https://t.co/example",
        created_at=datetime(2026, 5, 17, 0, 0, tzinfo=timezone.utc),
        author_id="1",
        author_name="作者",
        author_username="creator",
    )
    service = XTimelineDigestService(text_ai_client=_ReplyTextAI())

    service.add_reply_suggestions([post], project_id=project.id, reply_as=["ノア", "ラプ"])
    markdown = service.render_markdown([post], include_reply_suggestions=True)

    assert "[作者 (@creator)](https://x.com/creator/status/123)" in markdown
    assert "ノア: 朝の空気がきれいですね。少し元気をもらいました。" in markdown
    assert "ラプラス: いいね、この感じ。ちょっと好きかも。" in markdown


def test_reply_character_resolution_prefers_exact_nickname(app):
    project = _create_project_with_reply_characters()
    service = XTimelineDigestService(text_ai_client=_ReplyTextAI())

    characters = service._resolve_reply_characters(project.id, ["ラプ"])

    assert [character.name for character in characters] == ["ラプラス"]


def test_reply_suggestions_fill_missing_characters(app):
    project = _create_project_with_reply_characters()
    post = XRecentPost(
        id="234",
        text="朝の写真です。",
        created_at=datetime(2026, 5, 17, 0, 0, tzinfo=timezone.utc),
        author_id="1",
        author_name="作者",
        author_username="creator",
    )
    service = XTimelineDigestService(text_ai_client=_PartialTextAI())

    service.add_reply_suggestions([post], project_id=project.id, reply_as=["ノア", "ラプ"])

    assert [item["character"] for item in post.reply_suggestions] == ["ノア", "ラプラス"]


def test_reply_suggestions_fall_back_without_posting(app):
    project = _create_project_with_reply_characters()
    post = XRecentPost(
        id="456",
        text="おはようございます。",
        created_at=datetime(2026, 5, 17, 0, 0, tzinfo=timezone.utc),
        author_id="1",
        author_name="作者",
        author_username="creator",
    )
    service = XTimelineDigestService(text_ai_client=_FailingTextAI())

    service.add_reply_suggestions([post], project_id=project.id, reply_as=["ノア"])

    assert post.reply_suggestions == [
        {"character": "ノア", "text": "おはようございます。今日もいい日になりますように。"}
    ]


def test_serialize_post_includes_media(app):
    post = XRecentPost(
        id="789",
        text="京都シリーズです",
        created_at=datetime(2026, 5, 17, 0, 0, tzinfo=timezone.utc),
        author_id="1",
        author_name="作者",
        author_username="creator",
        followed_by_me=True,
        follows_me=True,
        is_mutual_follow=True,
        reply_settings="following",
        media=[{"type": "photo", "media_url": "/media/projects/1/assets/x_observation_media/a.jpg"}],
    )

    data = XTimelineDigestService().serialize_post(post)

    assert data["url"] == "https://x.com/creator/status/789"
    assert data["is_mutual_follow"] is True
    assert data["reply_settings"] == "following"
    assert data["media"][0]["media_url"].endswith("a.jpg")


def test_generate_reply_for_post_returns_single_clean_comment(app):
    project = _create_project_with_reply_characters()
    detail = XRecentPost(
        id="999",
        text="朝のイラストです",
        created_at=datetime(2026, 5, 17, 0, 0, tzinfo=timezone.utc),
        author_id="1",
        author_name="作者",
        author_username="creator",
    )
    service = XTimelineDigestService(text_ai_client=_SingleReplyTextAI())
    service.get_post_detail = lambda *_args, **_kwargs: detail

    result = service.generate_reply_for_post(project_id=project.id, tweet_id="999", character_id=1)

    assert result["character_name"] == "ノア"
    assert result["comment"] == "光の入り方がやわらかくて素敵ですね。"


def test_timeline_users_randomizes_from_sample_pool(monkeypatch):
    service = XTimelineDigestService()
    users = [SimpleNamespace(id=str(index), name=f"User {index}", username=f"user{index}") for index in range(6)]
    calls = []

    class _Client:
        def get_users_following(self, user_id, **kwargs):
            calls.append({"user_id": user_id, **kwargs})
            return SimpleNamespace(data=users[: kwargs["max_results"]], meta={})

    monkeypatch.setattr(
        "app.services.x_timeline_digest_service.random.sample",
        lambda pool, count: list(reversed(pool))[:count],
    )

    selected = service._timeline_users(
        _Client(),
        "me",
        max_users=2,
        source="following",
        randomize_users=True,
        user_sample_pool=6,
    )

    assert [user.id for user in selected] == ["5", "4"]
    assert calls[0]["max_results"] == 6


def test_home_timeline_posts_use_recent_unique_authors():
    service = XTimelineDigestService()
    now = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)
    users = [
        SimpleNamespace(id="1", name="One", username="one"),
        SimpleNamespace(id="2", name="Two", username="two"),
        SimpleNamespace(id="3", name="Three", username="three"),
    ]
    tweets = [
        SimpleNamespace(id="101", text="new one", author_id="1", created_at=now, public_metrics={}),
        SimpleNamespace(id="102", text="new one again", author_id="1", created_at=now, public_metrics={}),
        SimpleNamespace(id="201", text="new two", author_id="2", created_at=now, public_metrics={}),
        SimpleNamespace(id="301", text="old three", author_id="3", created_at=datetime(2026, 5, 15, tzinfo=timezone.utc), public_metrics={}),
    ]
    calls = []

    class _Client:
        def get_home_timeline(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(data=tweets, includes={"users": users})

    posts = service._home_timeline_posts(
        _Client(),
        cutoff=datetime(2026, 5, 16, tzinfo=timezone.utc),
        max_posts=10,
        tweets_per_user=1,
        include_replies=False,
        include_reposts=False,
    )

    assert [post.id for post in posts] == ["101", "201"]
    assert posts[0].followed_by_me is True
    assert calls[0]["max_results"] == 10
    assert calls[0]["exclude"] == ["replies", "retweets"]


def test_relationship_map_marks_mutual_following():
    service = XTimelineDigestService()
    selected_users = [
        SimpleNamespace(id="1", name="One", username="one"),
        SimpleNamespace(id="2", name="Two", username="two"),
    ]

    class _Client:
        def get_users_followers(self, user_id, **_kwargs):
            return SimpleNamespace(data=[SimpleNamespace(id="2"), SimpleNamespace(id="3")], meta={})

        def get_users_following(self, user_id, **_kwargs):
            return SimpleNamespace(data=selected_users, meta={})

    relationships = service._relationship_map_for_users(_Client(), "me", selected_users, source="following")

    assert relationships["1"] == {"followed_by_me": True, "follows_me": False, "is_mutual_follow": False}
    assert relationships["2"] == {"followed_by_me": True, "follows_me": True, "is_mutual_follow": True}
