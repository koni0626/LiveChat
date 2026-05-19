from __future__ import annotations

from app.services.x_trend_service import XTrend, XTrendService


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _Http:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return _Response(
            {
                "data": [
                    {"trend_name": "#NIKKE", "tweet_count": 120000},
                    {"trend_name": "政治ニュース", "tweet_count": 80000},
                    {"trend_name": "#ホラーゲーム", "tweet_count": None},
                ]
            }
        )

    def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return _Response({"access_token": "generated-bearer"})


def test_collect_trends_uses_bearer_token_and_filters_hashtags(app):
    app.config["X_BEARER_TOKEN"] = "bearer-token"
    http = _Http()
    service = XTrendService(http_client=http)

    trends = service.collect_trends(woeid="tokyo", max_trends=99, hashtags_only=True)

    assert [trend.name for trend in trends] == ["#NIKKE", "#ホラーゲーム"]
    assert trends[0].category == "game"
    assert trends[0].laplace_fit == "high"
    assert http.calls[0]["url"].endswith("/1118370")
    assert http.calls[0]["headers"]["Authorization"] == "Bearer bearer-token"
    assert http.calls[0]["params"]["max_trends"] == 50


def test_collect_trends_can_generate_app_only_bearer(app):
    app.config["X_BEARER_TOKEN"] = ""
    app.config["X_API_KEY"] = "key"
    app.config["X_API_SECRET"] = "secret"
    http = _Http()
    service = XTrendService(http_client=http)

    service.collect_trends(woeid="japan", max_trends=5)

    assert http.calls[0]["url"] == "https://api.x.com/oauth2/token"
    assert http.calls[1]["headers"]["Authorization"] == "Bearer generated-bearer"


def test_render_markdown_includes_noah_angles(app):
    service = XTrendService()
    trends = [
        XTrend(name="#NIKKE", tweet_count=120000, category="game", laplace_fit="high"),
        XTrend(name="普通の話題", category="other", laplace_fit="skip"),
    ]

    markdown = service.render_markdown(trends, woeid="japan", limit=2)

    assert "| #NIKKE | 120,000 | game | high | ゲーム内キャラ紹介風" in markdown
    assert "無理に乗らず" in markdown


def test_categorize_vtuber_reveal_tags():
    service = XTrendService()

    assert service.categorize("#らでん新衣装お披露目3Dライブ") == "vtuber"
