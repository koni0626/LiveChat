from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import base64
from typing import Any

from flask import current_app
import requests


@dataclass
class XTrend:
    name: str
    tweet_count: int | None = None
    category: str = "other"
    laplace_fit: str = "low"

    @property
    def is_hashtag(self) -> bool:
        return self.name.startswith("#")


class XTrendService:
    API_URL = "https://api.x.com/2/trends/by/woeid/{woeid}"
    TOKEN_URL = "https://api.x.com/oauth2/token"
    DEFAULT_WOEIDS = {
        "worldwide": 1,
        "japan": 23424856,
        "tokyo": 1118370,
        "united_states": 23424977,
    }

    CATEGORY_KEYWORDS = {
        "game": ("ゲーム", "任天堂", "Switch", "PS5", "Steam", "RPG", "ガチャ", "NIKKE", "ブルアカ", "原神", "スタレ", "ゼンゼロ", "FGO"),
        "anime": ("アニメ", "漫画", "マンガ", "ジャンプ", "声優", "映画", "劇場版"),
        "vtuber": ("VTuber", "Vtuber", "ホロライブ", "にじさんじ", "配信", "切り抜き", "3Dライブ", "お披露目", "新衣装"),
        "creative": ("イラスト", "創作", "絵描き", "AIイラスト", "一次創作", "小説"),
        "horror": ("ホラー", "怪談", "都市伝説", "怖い", "廃墟", "SCP"),
        "ai": ("AI", "生成AI", "ChatGPT", "Claude", "Gemini", "Grok"),
        "daily": ("月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜", "仕事", "眠い", "おはよう", "祝日"),
    }

    LAPACE_FIT_CATEGORIES = {"game", "anime", "vtuber", "creative", "horror", "ai", "daily"}

    def __init__(self, *, http_client: Any | None = None) -> None:
        self._http = http_client or requests

    def is_configured(self) -> bool:
        return bool(current_app.config.get("X_BEARER_TOKEN")) or bool(
            current_app.config.get("X_API_KEY") and current_app.config.get("X_API_SECRET")
        )

    def collect_trends(
        self,
        *,
        woeid: int | str = "japan",
        max_trends: int = 50,
        hashtags_only: bool = False,
    ) -> list[XTrend]:
        if not self.is_configured():
            raise RuntimeError("X_BEARER_TOKEN or X_API_KEY/X_API_SECRET is not configured")
        resolved_woeid = self.resolve_woeid(woeid)
        response = self._http.get(
            self.API_URL.format(woeid=resolved_woeid),
            headers={"Authorization": f"Bearer {self._bearer_token()}"},
            params={"max_trends": max(1, min(50, int(max_trends or 50)))},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        trends = [self._trend_from_api_row(row) for row in payload.get("data") or []]
        if hashtags_only:
            trends = [trend for trend in trends if trend.is_hashtag]
        return trends

    def resolve_woeid(self, value: int | str) -> int:
        key = str(value or "").strip().lower().replace("-", "_")
        if key in self.DEFAULT_WOEIDS:
            return self.DEFAULT_WOEIDS[key]
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"unknown WOEID: {value}") from exc

    def _bearer_token(self) -> str:
        token = str(current_app.config.get("X_BEARER_TOKEN") or "").strip()
        if token:
            return token
        key = str(current_app.config.get("X_API_KEY") or "").strip()
        secret = str(current_app.config.get("X_API_SECRET") or "").strip()
        if not key or not secret:
            raise RuntimeError("X_BEARER_TOKEN or X_API_KEY/X_API_SECRET is not configured")
        credentials = base64.b64encode(f"{key}:{secret}".encode("utf-8")).decode("ascii")
        response = self._http.post(
            self.TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
            data={"grant_type": "client_credentials"},
            timeout=30,
        )
        response.raise_for_status()
        token = str((response.json() or {}).get("access_token") or "").strip()
        if not token:
            raise RuntimeError("X OAuth2 token response did not include an access token")
        return token

    def render_markdown(
        self,
        trends: list[XTrend],
        *,
        woeid: int | str = "japan",
        hashtags_only: bool = False,
        limit: int | None = None,
    ) -> str:
        now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
        title = f"## X trends for {woeid} ({now})"
        if hashtags_only:
            title += " - hashtags only"
        if not trends:
            return f"{title}\n\nNo trends found."

        selected = trends[: max(1, int(limit))] if limit else trends
        lines = [title, "", "| Trend | Count | Category | Laplace fit | Noah angle |", "|---|---:|---|---|---|"]
        for trend in selected:
            count = f"{trend.tweet_count:,}" if trend.tweet_count is not None else "-"
            lines.append(
                f"| {self._escape_table(trend.name)} | {count} | {trend.category} | {trend.laplace_fit} | "
                f"{self._escape_table(self.noah_angle_for_trend(trend))} |"
            )
        return "\n".join(lines)

    def noah_angle_for_trend(self, trend: XTrend) -> str:
        if trend.category == "game":
            return "ゲーム内キャラ紹介風に、ノアが静かに参戦した体で触れる"
        if trend.category == "anime":
            return "感想ではなく、ノアの観測コメントとして短く乗る"
        if trend.category == "vtuber":
            return "市内放送や配信者ノアの一言として混ぜる"
        if trend.category == "creative":
            return "制作ログ、衣装差分、世界観設定に接続する"
        if trend.category == "horror":
            return "ラプラスシティの怪異・都市伝説として翻訳する"
        if trend.category == "ai":
            return "AI論ではなく、キャラ制作ワークフローとして語る"
        if trend.category == "daily":
            return "日常あるあるをラプラスシティ語に変換する"
        return "無理に乗らず、ノアの人格に合う切り口がある時だけ使う"

    def _trend_from_api_row(self, row: dict[str, Any]) -> XTrend:
        name = str(row.get("trend_name") or row.get("name") or "").strip()
        tweet_count = row.get("tweet_count")
        try:
            normalized_count = int(tweet_count) if tweet_count is not None else None
        except (TypeError, ValueError):
            normalized_count = None
        category = self.categorize(name)
        return XTrend(
            name=name,
            tweet_count=normalized_count,
            category=category,
            laplace_fit=self._laplace_fit(category, name),
        )

    def categorize(self, name: str) -> str:
        normalized = str(name or "")
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(keyword.lower() in normalized.lower() for keyword in keywords):
                return category
        return "other"

    def _laplace_fit(self, category: str, name: str) -> str:
        if category in {"game", "horror", "creative", "vtuber"}:
            return "high"
        if category in self.LAPACE_FIT_CATEGORIES:
            return "medium"
        return "low" if str(name or "").startswith("#") else "skip"

    def _escape_table(self, value: str) -> str:
        return str(value or "").replace("|", "\\|").replace("\n", " ")
