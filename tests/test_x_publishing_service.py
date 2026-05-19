from types import SimpleNamespace

from app.services.x_publishing_service import XPublishingService


def test_split_thread_keeps_short_text_as_single_post():
    service = XPublishingService()

    assert service.split_thread("人類は、プリンで滅びました。") == ["人類は、プリンで滅びました。"]


def test_split_thread_splits_long_japanese_text_with_markers():
    service = XPublishingService()
    text = (
        "人類はプリンで滅びました。"
        "宗教、資源、責任逃れ、メンツ、報復兵器が絡みました。"
        "それでも未来の教材では、だいたいプリンだったと教えています。"
    ) * 8

    parts = service.split_thread(text)

    assert len(parts) > 1
    assert parts[0].endswith(f"(1/{len(parts)})")
    assert parts[-1].endswith(f"({len(parts)}/{len(parts)})")
    assert all(service._tweet_weight(part) <= service.TWEET_WEIGHT_LIMIT for part in parts)
    assert "プリン" in parts[0]


def test_publish_feed_post_creates_reply_thread_for_long_post(monkeypatch, app):
    service = XPublishingService()
    created = []
    app.config.update(
        X_API_KEY="key",
        X_API_SECRET="secret",
        X_ACCESS_TOKEN="token",
        X_ACCESS_TOKEN_SECRET="token-secret",
        X_BEARER_TOKEN="bearer",
    )

    class _Client:
        def __init__(self, **_kwargs):
            pass

        def create_tweet(self, **kwargs):
            created.append(kwargs)
            return SimpleNamespace(data={"id": str(len(created)), "text": kwargs["text"]})

    class _Tweepy:
        Client = _Client

    monkeypatch.setattr(service, "is_configured", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "tweepy", _Tweepy)

    post = SimpleNamespace(body=("ラプラスシティでは、最後のプリンをめぐって会議が始まりました。" * 20))
    result = service.publish_feed_post(post)

    assert result["x_post_id"] == "1"
    assert result["thread_count"] == len(created)
    assert len(created) > 1
    assert "in_reply_to_tweet_id" not in created[0]
    assert created[1]["in_reply_to_tweet_id"] == "1"
    assert all(service._tweet_weight(item["text"]) <= service.TWEET_WEIGHT_LIMIT for item in created)


def test_publish_reply_creates_reply_to_target_tweet(monkeypatch, app):
    service = XPublishingService()
    created = []
    app.config.update(
        X_API_KEY="key",
        X_API_SECRET="secret",
        X_ACCESS_TOKEN="token",
        X_ACCESS_TOKEN_SECRET="token-secret",
        X_BEARER_TOKEN="bearer",
    )

    class _Client:
        def __init__(self, **_kwargs):
            pass

        def create_tweet(self, **kwargs):
            created.append(kwargs)
            return SimpleNamespace(data={"id": "reply-1", "text": kwargs["text"]})

    class _Tweepy:
        Client = _Client

    monkeypatch.setattr(service, "is_configured", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "tweepy", _Tweepy)

    result = service.publish_reply("target-1", "  光が綺麗ですね。  ")

    assert created == [{"text": "光が綺麗ですね。", "in_reply_to_tweet_id": "target-1"}]
    assert result["x_post_id"] == "reply-1"
    assert result["url"] == "https://x.com/i/web/status/reply-1"


def test_publish_reply_rejects_empty_text(app):
    service = XPublishingService()

    try:
        service.publish_reply("target-1", " ")
    except ValueError as exc:
        assert "reply text" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_publish_reply_returns_friendly_x_error(monkeypatch, app):
    service = XPublishingService()
    app.config.update(
        X_API_KEY="key",
        X_API_SECRET="secret",
        X_ACCESS_TOKEN="token",
        X_ACCESS_TOKEN_SECRET="token-secret",
        X_BEARER_TOKEN="bearer",
    )

    class _Client:
        def __init__(self, **_kwargs):
            pass

        def create_tweet(self, **_kwargs):
            error = RuntimeError("403 Forbidden")
            error.api_messages = ["You currently have Essential access"]
            raise error

    class _Tweepy:
        Client = _Client

    monkeypatch.setattr(service, "is_configured", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "tweepy", _Tweepy)

    try:
        service.publish_reply("target-1", "綺麗ですね。")
    except RuntimeError as exc:
        assert "X reply failed" in str(exc)
        assert "Essential access" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
