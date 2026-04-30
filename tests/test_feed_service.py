from types import SimpleNamespace

from app.services.feed_service import FeedService


class _Repo:
    def __init__(self):
        self.created = []

    def create_post(self, payload):
        post = SimpleNamespace(id=len(self.created) + 1, **payload)
        self.created.append(post)
        return post


class _Characters:
    def __init__(self, character):
        self.character = character

    def get_character(self, character_id):
        return self.character if character_id == self.character.id else None


def test_generate_posts_creates_published_post_and_generates_image(monkeypatch):
    character = SimpleNamespace(id=3, project_id=1, name="Noa")
    repo = _Repo()
    service = FeedService(repository=repo, character_service=_Characters(character))

    monkeypatch.setattr(
        service,
        "_generate_feed_candidates",
        lambda project_id, count: [{"character_id": character.id, "body": "今日は少しだけ特別な空気でした。"}],
    )
    monkeypatch.setattr(service, "refresh_character_feed_profile", lambda _character_id: None)
    generated = {"called": False}

    def generate_post_image(post_id, payload):
        generated["called"] = True
        post = repo.created[post_id - 1]
        post.image_asset_id = 42
        return post

    monkeypatch.setattr(service, "generate_post_image", generate_post_image)

    posts = service.generate_posts(project_id=1, user_id=2, payload={"count": 1})

    assert len(posts) == 1
    assert repo.created[0].status == "published"
    assert repo.created[0].image_asset_id == 42
    assert generated["called"] is True
