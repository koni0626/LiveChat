from datetime import datetime, timezone

from app.extensions import db
from app.models import User
from app.models.character import Character
from app.models.project import Project
from app.models.x_observation_reply import XObservationReply
from app.services.x_timeline_digest_service import XFollowUser, XRecentPost


def _create_observation_project():
    user = User(email="observe@example.com", display_name="Observer", password_hash="x", role="project_user")
    db.session.add(user)
    db.session.flush()
    project = Project(owner_user_id=user.id, title="Laplace", genre="fantasy", project_type="linear")
    db.session.add(project)
    db.session.flush()
    character = Character(project_id=project.id, name="Noa", nickname="Noa")
    db.session.add(character)
    db.session.commit()
    return project, character


class _FakeTimelineService:
    def __init__(self):
        self.calls = []
        self.post = XRecentPost(
            id="2055",
            text="朝のイラストです",
            created_at=datetime(2026, 5, 17, 0, 0, tzinfo=timezone.utc),
            author_id="1",
            author_name="Creator",
            author_username="creator",
            media=[{"type": "photo", "media_url": "/media/projects/1/assets/x_observation_media/a.jpg"}],
        )

    def collect_recent_posts(self, **kwargs):
        self.calls.append(("collect", kwargs))
        return [self.post]

    def get_post_detail(self, tweet_id, *, project_id=None):
        self.calls.append(("detail", {"tweet_id": tweet_id, "project_id": project_id}))
        return self.post

    def generate_reply_for_post(self, **kwargs):
        self.calls.append(("comment", kwargs))
        return {
            "tweet": self.serialize_post(self.post),
            "character_id": kwargs["character_id"],
            "character_name": "Noa",
            "comment": "光がやわらかくて、とても綺麗ですね。",
        }

    def serialize_post(self, post):
        return {
            "id": post.id,
            "text": post.text,
            "created_at": post.created_at.isoformat(),
            "author_id": post.author_id,
            "author_name": post.author_name,
            "author_username": post.author_username,
            "url": post.url,
            "like_count": post.like_count,
            "repost_count": post.repost_count,
            "reply_count": post.reply_count,
            "quote_count": post.quote_count,
            "media": post.media or [],
            "reply_suggestions": post.reply_suggestions or [],
        }

    def list_non_mutual_following(self, **kwargs):
        self.calls.append(("follow_cleanup_candidates", kwargs))
        return [
            XFollowUser(id="10", name="Solo", username="solo", description="not mutual", followers_count=12),
            XFollowUser(id="20", name="Quiet", username="quiet", followers_count=4),
        ]

    def serialize_follow_user(self, user):
        return {
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "description": user.description,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "url": user.url,
        }

    def unfollow_users(self, user_ids):
        self.calls.append(("unfollow_users", list(user_ids)))
        return [{"user_id": user_id, "ok": user_id != "20"} for user_id in user_ids]


class _FakePublishingService:
    def __init__(self):
        self.calls = []

    def publish_reply(self, tweet_id, text):
        self.calls.append({"tweet_id": tweet_id, "text": text})
        return {
            "x_post_id": "reply-2055",
            "in_reply_to_tweet_id": str(tweet_id),
            "text": text.strip(),
            "url": "https://x.com/i/web/status/reply-2055",
        }


def test_observations_page_opens_for_project_owner(client, app):
    project, _character = _create_observation_project()
    with client.session_transaction() as flask_session:
        flask_session["user_id"] = project.owner_user_id

    response = client.get(f"/projects/{project.id}/observations")

    assert response.status_code == 200
    assert "観測".encode("utf-8") in response.data


def test_observations_recent_detail_and_comment_endpoints(client, app, monkeypatch):
    project, character = _create_observation_project()
    fake = _FakeTimelineService()
    import app.blueprints.observations.routes as routes

    monkeypatch.setattr(routes, "timeline_service", fake)
    with client.session_transaction() as flask_session:
        flask_session["user_id"] = project.owner_user_id

    recent = client.get(
        f"/api/v1/projects/{project.id}/observations/x/recent",
        query_string={"source": "followers", "hours": 12, "max_users": 8, "user_sample_pool": 80, "tweets_per_user": 2},
    )
    assert recent.status_code == 200
    recent_data = recent.get_json()["data"]
    assert recent_data["filters"]["source"] == "followers"
    assert recent_data["filters"]["randomize_users"] is True
    assert recent_data["filters"]["user_sample_pool"] == 80
    assert recent_data["items"][0]["url"] == "https://x.com/creator/status/2055"
    assert fake.calls[0][1]["include_replies"] is False
    assert fake.calls[0][1]["include_reposts"] is False
    assert fake.calls[0][1]["randomize_users"] is True
    assert fake.calls[0][1]["user_sample_pool"] == 80

    detail = client.get(f"/api/v1/projects/{project.id}/observations/x/posts/2055")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["media"][0]["media_url"].endswith("a.jpg")

    comment = client.post(
        f"/api/v1/projects/{project.id}/observations/x/posts/2055/comment",
        json={"character_id": character.id},
    )
    assert comment.status_code == 200
    comment_data = comment.get_json()["data"]
    assert comment_data["character_id"] == character.id
    assert "綺麗" in comment_data["comment"]


def test_observations_reply_endpoint_publishes_and_records_reply(client, app, monkeypatch):
    project, _character = _create_observation_project()
    import app.blueprints.observations.routes as routes

    fake_publishing = _FakePublishingService()
    monkeypatch.setattr(routes, "x_publishing_service", fake_publishing)
    with client.session_transaction() as flask_session:
        flask_session["user_id"] = project.owner_user_id

    response = client.post(
        f"/api/v1/projects/{project.id}/observations/x/posts/2055/reply",
        json={
            "text": "光の感じがとても綺麗ですね。",
            "target": {
                "author_id": "1",
                "author_name": "Creator",
                "author_username": "creator",
            },
        },
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["x_post_id"] == "reply-2055"
    assert data["url"] == "https://x.com/i/web/status/reply-2055"
    assert data["text"] == "光の感じがとても綺麗ですね。"
    assert fake_publishing.calls == [{"tweet_id": "2055", "text": "光の感じがとても綺麗ですね。"}]

    row = XObservationReply.query.filter_by(project_id=project.id, target_tweet_id="2055").one()
    assert row.reply_text == "光の感じがとても綺麗ですね。"
    assert row.reply_x_post_id == "reply-2055"
    assert row.target_author_username == "creator"

    monkeypatch.setattr(routes, "timeline_service", _FakeTimelineService())
    detail = client.get(f"/api/v1/projects/{project.id}/observations/x/posts/2055")
    detail_data = detail.get_json()["data"]
    assert detail_data["is_replied"] is True
    assert detail_data["observation_reply"]["reply_text"] == "光の感じがとても綺麗ですね。"


def test_observations_mark_replied_endpoint_records_manual_reply_done(client, app):
    project, _character = _create_observation_project()
    with client.session_transaction() as flask_session:
        flask_session["user_id"] = project.owner_user_id

    response = client.post(
        f"/api/v1/projects/{project.id}/observations/x/posts/2055/mark-replied",
        json={
            "text": "手動で返信しました。",
            "target": {
                "author_id": "1",
                "author_name": "Creator",
                "author_username": "creator",
            },
        },
    )

    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["manual"] is True
    assert data["x_post_id"] == ""
    assert data["url"] == ""

    row = XObservationReply.query.filter_by(project_id=project.id, target_tweet_id="2055").one()
    assert row.reply_text == "手動で返信しました。"
    assert row.reply_x_post_id is None


def test_observations_follow_cleanup_candidates_and_unfollow(client, app, monkeypatch):
    project, _character = _create_observation_project()
    fake = _FakeTimelineService()
    import app.blueprints.observations.routes as routes

    monkeypatch.setattr(routes, "timeline_service", fake)
    with client.session_transaction() as flask_session:
        flask_session["user_id"] = project.owner_user_id

    candidates = client.get(
        f"/api/v1/projects/{project.id}/observations/x/follow-cleanup/candidates",
        query_string={"max_users": 200},
    )
    assert candidates.status_code == 200
    candidate_data = candidates.get_json()["data"]
    assert candidate_data["count"] == 2
    assert candidate_data["items"][0]["username"] == "solo"
    assert fake.calls[-1] == ("follow_cleanup_candidates", {"max_users": 200})

    unfollow = client.post(
        f"/api/v1/projects/{project.id}/observations/x/follow-cleanup/unfollow",
        json={"user_ids": ["10", "20"]},
    )
    assert unfollow.status_code == 200
    unfollow_data = unfollow.get_json()["data"]
    assert unfollow_data["success_count"] == 1
    assert unfollow_data["failure_count"] == 1
    assert fake.calls[-1] == ("unfollow_users", ["10", "20"])
