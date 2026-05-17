from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app

from ..clients.text_ai_client import TextAIClient
from ..repositories.character_repository import CharacterRepository
from ..utils import json_util


@dataclass
class XRecentPost:
    id: str
    text: str
    created_at: datetime
    author_id: str
    author_name: str
    author_username: str
    like_count: int = 0
    repost_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    reply_suggestions: list[dict[str, str]] | None = None

    @property
    def url(self) -> str:
        return f"https://x.com/{self.author_username}/status/{self.id}"


class XTimelineDigestService:
    def __init__(
        self,
        *,
        text_ai_client: TextAIClient | None = None,
        character_repository: CharacterRepository | None = None,
    ) -> None:
        self._text_ai_client = text_ai_client or TextAIClient()
        self._characters = character_repository or CharacterRepository()

    def is_configured(self) -> bool:
        return all(
            current_app.config.get(key)
            for key in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
        )

    def collect_recent_following_posts(
        self,
        *,
        hours: int = 24,
        max_users: int = 100,
        tweets_per_user: int = 5,
        include_replies: bool = False,
        include_reposts: bool = False,
    ) -> list[XRecentPost]:
        if not self.is_configured():
            raise RuntimeError("X API keys are not configured")
        try:
            import tweepy
        except ImportError as exc:
            raise RuntimeError("tweepy is required. Run pip install -r requirements.txt") from exc

        client = self._client(tweepy)
        me_response = client.get_me(user_auth=True)
        me = getattr(me_response, "data", None)
        if not me:
            raise RuntimeError("Could not resolve authenticated X user")

        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(hours or 24)))
        following = self._following_users(client, str(me.id), max_users=max_users)
        posts: list[XRecentPost] = []
        for user in following:
            posts.extend(
                self._recent_posts_for_user(
                    client,
                    user,
                    cutoff=cutoff,
                    tweets_per_user=tweets_per_user,
                    include_replies=include_replies,
                    include_reposts=include_reposts,
                )
            )
        return sorted(posts, key=lambda item: item.created_at, reverse=True)

    def add_reply_suggestions(
        self,
        posts: list[XRecentPost],
        *,
        project_id: int,
        reply_as: list[str] | tuple[str, ...] | None = None,
        limit: int = 20,
        model: str | None = None,
    ) -> list[XRecentPost]:
        if not posts:
            return posts
        characters = self._resolve_reply_characters(project_id, reply_as or ["ノア", "ラプ"])
        if not characters:
            raise RuntimeError("Reply characters were not found")
        for post in posts[: max(1, int(limit or 20))]:
            post.reply_suggestions = self._generate_reply_suggestions(post, characters, model=model)
        return posts

    def render_markdown(self, posts: list[XRecentPost], *, hours: int = 24, include_reply_suggestions: bool = False) -> str:
        if not posts:
            return f"## X recent posts\n\nNo posts found in the last {hours} hours."
        lines = [f"## X recent posts in the last {hours} hours", ""]
        for post in posts:
            created = post.created_at.astimezone().strftime("%Y-%m-%d %H:%M")
            text = self._compact_text(post.text)
            metrics = []
            if post.like_count:
                metrics.append(f"likes {post.like_count}")
            if post.repost_count:
                metrics.append(f"reposts {post.repost_count}")
            metric_text = f" ({', '.join(metrics)})" if metrics else ""
            lines.append(
                f"- [{post.author_name} (@{post.author_username})]({post.url}) - {created}{metric_text}\n"
                f"  {text}"
            )
            if include_reply_suggestions and post.reply_suggestions:
                for suggestion in post.reply_suggestions:
                    speaker = suggestion.get("character") or "返信案"
                    body = self._compact_text(suggestion.get("text") or "", limit=140)
                    if body:
                        lines.append(f"  - {speaker}: {body}")
        return "\n".join(lines)

    def _client(self, tweepy):
        return tweepy.Client(
            bearer_token=current_app.config.get("X_BEARER_TOKEN") or None,
            consumer_key=current_app.config["X_API_KEY"],
            consumer_secret=current_app.config["X_API_SECRET"],
            access_token=current_app.config["X_ACCESS_TOKEN"],
            access_token_secret=current_app.config["X_ACCESS_TOKEN_SECRET"],
            wait_on_rate_limit=True,
        )

    def _following_users(self, client, user_id: str, *, max_users: int):
        users = []
        paginator = client.get_users_following(
            user_id,
            max_results=min(1000, max(1, int(max_users or 100))),
            user_fields=["name", "username"],
            user_auth=True,
        )
        data = getattr(paginator, "data", None) or []
        for user in data:
            users.append(user)
            if len(users) >= max_users:
                break
        return users

    def _recent_posts_for_user(
        self,
        client,
        user,
        *,
        cutoff: datetime,
        tweets_per_user: int,
        include_replies: bool,
        include_reposts: bool,
    ) -> list[XRecentPost]:
        exclude = []
        if not include_replies:
            exclude.append("replies")
        if not include_reposts:
            exclude.append("retweets")
        response = client.get_users_tweets(
            str(user.id),
            max_results=max(5, min(100, int(tweets_per_user or 5))),
            tweet_fields=["created_at", "public_metrics", "referenced_tweets"],
            exclude=exclude or None,
            user_auth=True,
        )
        tweets = getattr(response, "data", None) or []
        items = []
        for tweet in tweets:
            created_at = getattr(tweet, "created_at", None)
            if not created_at:
                continue
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at < cutoff:
                continue
            metrics = getattr(tweet, "public_metrics", None) or {}
            items.append(
                XRecentPost(
                    id=str(tweet.id),
                    text=str(tweet.text or ""),
                    created_at=created_at,
                    author_id=str(user.id),
                    author_name=str(user.name or ""),
                    author_username=str(user.username or ""),
                    like_count=int(metrics.get("like_count") or 0),
                    repost_count=int(metrics.get("retweet_count") or 0),
                    reply_count=int(metrics.get("reply_count") or 0),
                    quote_count=int(metrics.get("quote_count") or 0),
                )
            )
        return items

    def _compact_text(self, text: str, *, limit: int = 180) -> str:
        value = " ".join(str(text or "").split())
        if len(value) <= limit:
            return value
        return value[:limit].rstrip() + "..."

    def _resolve_reply_characters(self, project_id: int, selectors: list[str] | tuple[str, ...]):
        characters = self._characters.list_by_project(project_id)
        wanted = [str(item or "").strip().lower() for item in selectors if str(item or "").strip()]
        if not wanted:
            wanted = ["ノア", "ラプ"]
        matched = []
        for selector in wanted:
            exact_match = None
            for character in characters:
                values = [
                    str(getattr(character, "name", "") or "").lower(),
                    str(getattr(character, "nickname", "") or "").lower(),
                ]
                if selector in values:
                    exact_match = character
                    break
            if exact_match is None:
                for character in characters:
                    values = [
                        str(getattr(character, "name", "") or "").lower(),
                        str(getattr(character, "nickname", "") or "").lower(),
                    ]
                    if any(value.startswith(selector) for value in values if value):
                        exact_match = character
                        break
            if exact_match is None:
                for character in characters:
                    values = [
                        str(getattr(character, "name", "") or "").lower(),
                        str(getattr(character, "nickname", "") or "").lower(),
                    ]
                    if any(selector in value for value in values if value):
                        exact_match = character
                        break
            if exact_match is not None:
                if exact_match not in matched:
                    matched.append(exact_match)
        return matched

    def _generate_reply_suggestions(self, post: XRecentPost, characters: list[Any], *, model: str | None = None) -> list[dict[str, str]]:
        prompt = self._reply_prompt(post, characters)
        try:
            result = self._text_ai_client.generate_text(
                prompt,
                model=model,
                temperature=0.7,
                response_format={"type": "json_object"},
                max_tokens=900,
            )
            parsed = json_util.loads(result.get("text") or "{}")
            suggestions = parsed.get("suggestions") if isinstance(parsed, dict) else None
            if isinstance(suggestions, list):
                normalized = self._normalize_reply_suggestions(suggestions, characters)
                if normalized:
                    return self._fill_missing_reply_suggestions(post, normalized, characters)
        except Exception:
            current_app.logger.exception("Failed to generate X reply suggestions")
        return self._fallback_reply_suggestions(post, characters)

    def _reply_prompt(self, post: XRecentPost, characters: list[Any]) -> str:
        character_lines = []
        for character in characters:
            character_lines.append(
                "\n".join(
                    [
                        f"- id: {character.id}",
                        f"  name: {character.name}",
                        f"  nickname: {character.nickname or ''}",
                        f"  first_person: {character.first_person or ''}",
                        f"  personality: {self._compact_text(character.personality or '', limit=220)}",
                        f"  speech_style: {self._compact_text(character.speech_style or '', limit=220)}",
                        f"  speech_sample: {self._compact_text(character.speech_sample or '', limit=220)}",
                        f"  ng_rules: {self._compact_text(character.ng_rules or '', limit=160)}",
                    ]
                )
            )
        return f"""
Xの投稿に対して、キャラクター本人が軽く返信する体の「手動返信用の候補」を作ってください。
返信は実際には投稿しません。ユーザーが良さそうなものだけ手動で使います。

制約:
- JSONだけ返す。形式: {{"suggestions":[{{"character_id":1,"character":"ノア","text":"..."}}]}}
- 各キャラクターにつき1案。
- 返信は日本語で、1文から2文、60文字以内。
- 相手を褒める、共感する、軽く拾う程度。宣伝、長文考察、濃い設定語りは禁止。
- 相手の投稿に画像URLが含まれていてもURLには触れない。
- ハッシュタグは付けない。
- 失礼、馴れ馴れしすぎ、炎上しそうな表現は避ける。
- キャラクターの口調は使うが、あだ名ではなく name を表示名として使う。

対象投稿:
author: {post.author_name} (@{post.author_username})
text: {post.text}

キャラクター:
{chr(10).join(character_lines)}
""".strip()

    def _normalize_reply_suggestions(self, suggestions: list[Any], characters: list[Any]) -> list[dict[str, str]]:
        by_id = {int(character.id): character for character in characters}
        by_name = {str(character.name): character for character in characters}
        normalized = []
        used_ids = set()
        for item in suggestions:
            if not isinstance(item, dict):
                continue
            character = None
            try:
                character_id = int(item.get("character_id") or 0)
            except (TypeError, ValueError):
                character_id = 0
            if character_id:
                character = by_id.get(character_id)
            if character is None:
                character = by_name.get(str(item.get("character") or ""))
            text = self._clean_reply_text(item.get("text") or "")
            if character is None or not text or character.id in used_ids:
                continue
            used_ids.add(character.id)
            normalized.append({"character": character.name, "text": text})
        return normalized

    def _clean_reply_text(self, text: str) -> str:
        value = " ".join(str(text or "").split())
        for marker in ("#", "http://", "https://"):
            if marker in value:
                value = value.split(marker, 1)[0].rstrip()
        return value[:120].strip()

    def _fallback_reply_suggestions(self, post: XRecentPost, characters: list[Any]) -> list[dict[str, str]]:
        text = str(post.text or "")
        suggestions = []
        for character in characters:
            name = str(character.name or "")
            if "ラプ" in name or "ラプ" in str(character.nickname or ""):
                body = "いいね、こういう空気。ちょっと好きかも。"
            elif "おは" in text:
                body = "おはようございます。今日もいい日になりますように。"
            else:
                body = "素敵ですね。見ていて少し元気をもらいました。"
            suggestions.append({"character": name, "text": body})
        return suggestions

    def _fill_missing_reply_suggestions(
        self,
        post: XRecentPost,
        suggestions: list[dict[str, str]],
        characters: list[Any],
    ) -> list[dict[str, str]]:
        existing_names = {item.get("character") for item in suggestions}
        missing = [character for character in characters if character.name not in existing_names]
        if not missing:
            return suggestions
        return suggestions + self._fallback_reply_suggestions(post, missing)
