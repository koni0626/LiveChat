from datetime import datetime, timezone

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
