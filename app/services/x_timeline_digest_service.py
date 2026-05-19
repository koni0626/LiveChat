from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import mimetypes
from pathlib import Path
import random
from typing import Any

from flask import current_app
import requests

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
    followed_by_me: bool | None = None
    follows_me: bool | None = None
    is_mutual_follow: bool | None = None
    reply_settings: str | None = None
    media: list[dict[str, Any]] | None = None
    reply_suggestions: list[dict[str, str]] | None = None

    @property
    def url(self) -> str:
        return f"https://x.com/{self.author_username}/status/{self.id}"


@dataclass
class XFollowUser:
    id: str
    name: str
    username: str
    description: str = ""
    followers_count: int = 0
    following_count: int = 0

    @property
    def url(self) -> str:
        return f"https://x.com/{self.username}" if self.username else "https://x.com/"


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
        return self.collect_recent_posts(
            hours=hours,
            max_users=max_users,
            tweets_per_user=tweets_per_user,
            include_replies=include_replies,
            include_reposts=include_reposts,
            source="following",
        )

    def collect_recent_posts(
        self,
        *,
        hours: int = 24,
        max_users: int = 100,
        tweets_per_user: int = 5,
        include_replies: bool = False,
        include_reposts: bool = False,
        source: str = "home_timeline",
        randomize_users: bool = False,
        user_sample_pool: int | None = None,
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
        source_key = str(source or "").lower()
        if source_key in {"home", "home_timeline", "timeline"}:
            return self._home_timeline_posts(
                client,
                cutoff=cutoff,
                max_posts=max_users,
                tweets_per_user=tweets_per_user,
                include_replies=include_replies,
                include_reposts=include_reposts,
            )
        users = self._timeline_users(
            client,
            str(me.id),
            max_users=max_users,
            source=source,
            randomize_users=randomize_users,
            user_sample_pool=user_sample_pool,
        )
        relationships = self._relationship_map_for_users(client, str(me.id), users, source=source)
        posts: list[XRecentPost] = []
        for user in users:
            relationship = relationships.get(str(getattr(user, "id", "") or ""), {})
            posts.extend(
                self._recent_posts_for_user(
                    client,
                    user,
                    cutoff=cutoff,
                    tweets_per_user=tweets_per_user,
                    include_replies=include_replies,
                    include_reposts=include_reposts,
                    relationship=relationship,
                )
            )
        return sorted(posts, key=lambda item: item.created_at, reverse=True)

    def get_post_detail(self, tweet_id: str, *, project_id: int | None = None) -> XRecentPost:
        if not self.is_configured():
            raise RuntimeError("X API keys are not configured")
        try:
            import tweepy
        except ImportError as exc:
            raise RuntimeError("tweepy is required. Run pip install -r requirements.txt") from exc
        client = self._client(tweepy)
        response = client.get_tweet(
            str(tweet_id),
            expansions=["attachments.media_keys", "author_id"],
            tweet_fields=["created_at", "public_metrics", "attachments", "reply_settings"],
            media_fields=["url", "preview_image_url", "alt_text", "type", "width", "height"],
            user_fields=["name", "username"],
            user_auth=True,
        )
        tweet = getattr(response, "data", None)
        if not tweet:
            raise RuntimeError("Could not resolve X post")
        users = {str(user.id): user for user in (getattr(response, "includes", None) or {}).get("users", [])}
        author = users.get(str(getattr(tweet, "author_id", "") or ""))
        media_items = self._media_items((getattr(response, "includes", None) or {}).get("media", []), project_id=project_id)
        return self._post_from_tweet(tweet, author, media=media_items)

    def generate_reply_for_post(
        self,
        *,
        project_id: int,
        tweet_id: str,
        character_id: int,
        model: str | None = None,
    ) -> dict[str, Any]:
        detail = self.get_post_detail(tweet_id, project_id=project_id)
        character = self._characters.get(int(character_id or 0))
        if not character or int(character.project_id) != int(project_id):
            raise ValueError("character_id is invalid")
        image_note = self._image_note(detail)
        prompt = self._single_reply_prompt(detail, character, image_note=image_note)
        try:
            result = self._text_ai_client.generate_text(
                prompt,
                model=model,
                temperature=0.65,
                response_format={"type": "json_object"},
                max_tokens=500,
            )
            parsed = json_util.loads(result.get("text") or "{}")
            text = self._clean_reply_text(parsed.get("comment") or parsed.get("text") or "")
            if text:
                return {
                    "tweet": self.serialize_post(detail),
                    "character_id": character.id,
                    "character_name": character.name,
                    "comment": text,
                    "image_note": image_note,
                }
        except Exception:
            current_app.logger.exception("Failed to generate X observation reply")
        fallback = self._fallback_reply_suggestions(detail, [character])[0]["text"]
        return {
            "tweet": self.serialize_post(detail),
            "character_id": character.id,
            "character_name": character.name,
            "comment": fallback,
            "image_note": image_note,
        }

    def serialize_post(self, post: XRecentPost) -> dict[str, Any]:
        return {
            "id": post.id,
            "text": post.text,
            "created_at": post.created_at.isoformat() if post.created_at else None,
            "author_id": post.author_id,
            "author_name": post.author_name,
            "author_username": post.author_username,
            "url": post.url,
            "like_count": post.like_count,
            "repost_count": post.repost_count,
            "reply_count": post.reply_count,
            "quote_count": post.quote_count,
            "followed_by_me": post.followed_by_me,
            "follows_me": post.follows_me,
            "is_mutual_follow": post.is_mutual_follow,
            "reply_settings": post.reply_settings,
            "media": post.media or [],
            "reply_suggestions": post.reply_suggestions or [],
        }

    def list_non_mutual_following(self, *, max_users: int = 5000) -> list[XFollowUser]:
        if not self.is_configured():
            raise RuntimeError("X API keys are not configured")
        try:
            import tweepy
        except ImportError as exc:
            raise RuntimeError("tweepy is required. Run pip install -r requirements.txt") from exc

        client = self._client(tweepy)
        me = getattr(client.get_me(user_auth=True), "data", None)
        if not me:
            raise RuntimeError("Could not resolve authenticated X user")
        following = self._timeline_users(client, str(me.id), max_users=max_users, source="following")
        follower_ids = self._timeline_user_id_set(client, str(me.id), source="followers", max_users=max_users)
        candidates = [
            self._follow_user_from_api_user(user)
            for user in following
            if str(getattr(user, "id", "") or "") and str(getattr(user, "id", "") or "") not in follower_ids
        ]
        return sorted(candidates, key=lambda item: item.username.lower())

    def unfollow_users(self, user_ids: list[str]) -> list[dict[str, Any]]:
        if not self.is_configured():
            raise RuntimeError("X API keys are not configured")
        ids = [str(user_id).strip() for user_id in user_ids if str(user_id).strip()]
        if not ids:
            raise ValueError("user_ids is required")
        try:
            import tweepy
        except ImportError as exc:
            raise RuntimeError("tweepy is required. Run pip install -r requirements.txt") from exc

        client = self._client(tweepy)
        results = []
        for user_id in ids:
            try:
                response = client.unfollow_user(user_id, user_auth=True)
                data = getattr(response, "data", None) or {}
                results.append({"user_id": user_id, "ok": True, "data": data})
            except Exception as exc:
                results.append({"user_id": user_id, "ok": False, "error": str(exc)})
        return results

    def serialize_follow_user(self, user: XFollowUser) -> dict[str, Any]:
        return {
            "id": user.id,
            "name": user.name,
            "username": user.username,
            "description": user.description,
            "followers_count": user.followers_count,
            "following_count": user.following_count,
            "url": user.url,
        }

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
        return self._timeline_users(client, user_id, max_users=max_users, source="following")

    def _timeline_users(
        self,
        client,
        user_id: str,
        *,
        max_users: int,
        source: str = "following",
        randomize_users: bool = False,
        user_sample_pool: int | None = None,
    ):
        users = []
        limit = max(1, int(max_users or 100))
        pool_limit = limit
        if randomize_users:
            pool_limit = max(limit, int(user_sample_pool or (limit * 5)))
            pool_limit = min(pool_limit, 5000)
        method = client.get_users_followers if str(source or "").lower() == "followers" else client.get_users_following
        next_token = None
        while len(users) < pool_limit:
            kwargs = {
                "max_results": min(1000, max(1, pool_limit - len(users))),
                "user_fields": ["name", "username", "description", "public_metrics"],
                "user_auth": True,
            }
            if next_token:
                kwargs["pagination_token"] = next_token
            response = method(user_id, **kwargs)
            data = getattr(response, "data", None) or []
            users.extend(data)
            meta = getattr(response, "meta", None) or {}
            next_token = meta.get("next_token") if isinstance(meta, dict) else None
            if not next_token or not data:
                break
        if randomize_users:
            if len(users) > limit:
                return random.sample(users, limit)
            random.shuffle(users)
        return users[:limit]

    def _home_timeline_posts(
        self,
        client,
        *,
        cutoff: datetime,
        max_posts: int,
        tweets_per_user: int,
        include_replies: bool,
        include_reposts: bool,
    ) -> list[XRecentPost]:
        limit = max(1, int(max_posts or 50))
        per_user_limit = max(1, int(tweets_per_user or 1))
        exclude = []
        if not include_replies:
            exclude.append("replies")
        if not include_reposts:
            exclude.append("retweets")
        response = client.get_home_timeline(
            max_results=max(5, min(100, limit * per_user_limit)),
            tweet_fields=["created_at", "public_metrics", "referenced_tweets", "reply_settings", "author_id"],
            expansions=["author_id"],
            user_fields=["name", "username"],
            exclude=exclude or None,
            user_auth=True,
        )
        tweets = getattr(response, "data", None) or []
        includes = getattr(response, "includes", None) or {}
        users = {str(getattr(user, "id", "") or ""): user for user in includes.get("users", [])}
        per_user_counts: dict[str, int] = {}
        items: list[XRecentPost] = []
        for tweet in tweets:
            created_at = self._created_at(tweet)
            if created_at < cutoff:
                continue
            author_id = str(getattr(tweet, "author_id", "") or "")
            if per_user_counts.get(author_id, 0) >= per_user_limit:
                continue
            author = users.get(author_id)
            if not author:
                continue
            per_user_counts[author_id] = per_user_counts.get(author_id, 0) + 1
            items.append(self._post_from_tweet(tweet, author, relationship={"followed_by_me": True}))
            if len(items) >= limit:
                break
        return items

    def _recent_posts_for_user(
        self,
        client,
        user,
        *,
        cutoff: datetime,
        tweets_per_user: int,
        include_replies: bool,
        include_reposts: bool,
        relationship: dict[str, bool] | None = None,
    ) -> list[XRecentPost]:
        exclude = []
        if not include_replies:
            exclude.append("replies")
        if not include_reposts:
            exclude.append("retweets")
        response = client.get_users_tweets(
            str(user.id),
            max_results=max(5, min(100, int(tweets_per_user or 5))),
            tweet_fields=["created_at", "public_metrics", "referenced_tweets", "reply_settings"],
            exclude=exclude or None,
            user_auth=True,
        )
        tweets = getattr(response, "data", None) or []
        items = []
        for tweet in tweets:
            created_at = self._created_at(tweet)
            if created_at < cutoff:
                continue
            items.append(self._post_from_tweet(tweet, user, relationship=relationship))
        return items

    def _post_from_tweet(
        self,
        tweet,
        user,
        *,
        media: list[dict[str, Any]] | None = None,
        relationship: dict[str, bool] | None = None,
    ) -> XRecentPost:
        metrics = getattr(tweet, "public_metrics", None) or {}
        relationship = relationship or {}
        return XRecentPost(
            id=str(tweet.id),
            text=str(tweet.text or ""),
            created_at=self._created_at(tweet),
            author_id=str(getattr(user, "id", "") or getattr(tweet, "author_id", "") or ""),
            author_name=str(getattr(user, "name", "") or ""),
            author_username=str(getattr(user, "username", "") or ""),
            like_count=int(metrics.get("like_count") or 0),
            repost_count=int(metrics.get("retweet_count") or 0),
            reply_count=int(metrics.get("reply_count") or 0),
            quote_count=int(metrics.get("quote_count") or 0),
            followed_by_me=relationship.get("followed_by_me"),
            follows_me=relationship.get("follows_me"),
            is_mutual_follow=relationship.get("is_mutual_follow"),
            reply_settings=getattr(tweet, "reply_settings", None),
            media=media or [],
        )

    def _relationship_map_for_users(self, client, user_id: str, users: list[Any], *, source: str) -> dict[str, dict[str, bool]]:
        user_ids = {str(getattr(user, "id", "") or "") for user in users}
        user_ids.discard("")
        if not user_ids:
            return {}
        source_key = str(source or "").lower()
        if source_key == "followers":
            follower_ids = set(user_ids)
            following_ids = self._timeline_user_id_set(client, user_id, source="following", max_users=5000)
        else:
            following_ids = set(user_ids)
            follower_ids = self._timeline_user_id_set(client, user_id, source="followers", max_users=5000)
        relationships = {}
        for target_id in user_ids:
            followed_by_me = target_id in following_ids
            follows_me = target_id in follower_ids
            relationships[target_id] = {
                "followed_by_me": followed_by_me,
                "follows_me": follows_me,
                "is_mutual_follow": followed_by_me and follows_me,
            }
        return relationships

    def _timeline_user_id_set(self, client, user_id: str, *, source: str, max_users: int = 5000) -> set[str]:
        return {str(getattr(user, "id", "") or "") for user in self._timeline_users(client, user_id, max_users=max_users, source=source)}

    def _follow_user_from_api_user(self, user) -> XFollowUser:
        metrics = getattr(user, "public_metrics", None) or {}
        return XFollowUser(
            id=str(getattr(user, "id", "") or ""),
            name=str(getattr(user, "name", "") or ""),
            username=str(getattr(user, "username", "") or ""),
            description=self._compact_text(getattr(user, "description", "") or "", limit=160),
            followers_count=int(metrics.get("followers_count") or 0),
            following_count=int(metrics.get("following_count") or 0),
        )

    def _created_at(self, tweet) -> datetime:
        created_at = getattr(tweet, "created_at", None)
        if not created_at:
            created_at = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        return created_at

    def _media_items(self, media_rows: list[Any], *, project_id: int | None = None) -> list[dict[str, Any]]:
        items = []
        for media in media_rows or []:
            original_url = getattr(media, "url", None) or getattr(media, "preview_image_url", None)
            item = {
                "media_key": getattr(media, "media_key", None),
                "type": getattr(media, "type", None),
                "url": original_url,
                "width": getattr(media, "width", None),
                "height": getattr(media, "height", None),
                "alt_text": getattr(media, "alt_text", None),
            }
            if project_id and original_url and str(item.get("type") or "") == "photo":
                local = self._download_observation_media(project_id, original_url, str(item.get("media_key") or "media"))
                item.update(local)
            items.append(item)
        return items

    def _download_observation_media(self, project_id: int, url: str, media_key: str) -> dict[str, Any]:
        storage_root = current_app.config.get("STORAGE_ROOT")
        output_dir = Path(storage_root) / "projects" / str(project_id) / "assets" / "x_observation_media"
        output_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(str(url).encode("utf-8")).hexdigest()[:16]
        ext = Path(str(url).split("?", 1)[0]).suffix.lower() or ".jpg"
        if ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            ext = ".jpg"
        file_name = f"{media_key}_{digest}{ext}"
        file_path = output_dir / file_name
        if not file_path.exists():
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            file_path.write_bytes(response.content)
        relative = file_path.relative_to(Path(storage_root)).as_posix()
        return {
            "local_file_path": str(file_path),
            "media_url": f"/media/{relative}",
            "mime_type": mimetypes.guess_type(str(file_path))[0] or "image/jpeg",
            "file_size": file_path.stat().st_size,
        }

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

    def _single_reply_prompt(self, post: XRecentPost, character: Any, *, image_note: str = "") -> str:
        return f"""
Xの投稿に対して、{character.name} が話している体の手動返信候補を1つ作ってください。
実際には自動投稿しません。ユーザーが見て良ければ手動で返信します。

制約:
- JSONだけ返す。形式: {{"comment":"..."}}
- 日本語で1文から2文、80文字以内。
- ハッシュタグ、URL、自分の宣伝、投稿誘導は禁止。
- 本文のセリフより、画像の表情・衣装・光・背景・構図への反応を優先する。
- 薄く、可愛く、具体的に褒める。
- 失礼、過度に馴れ馴れしい、性的に強すぎる表現は避ける。
- キャラクター口調は自然に使うが、設定語りはしない。

キャラクター:
name: {character.name}
nickname: {character.nickname or ""}
first_person: {character.first_person or ""}
personality: {self._compact_text(character.personality or "", limit=220)}
speech_style: {self._compact_text(character.speech_style or "", limit=220)}
speech_sample: {self._compact_text(character.speech_sample or "", limit=220)}
ng_rules: {self._compact_text(character.ng_rules or "", limit=160)}

対象投稿:
author: {post.author_name} (@{post.author_username})
text: {post.text}

画像メモ:
{image_note or "画像メモなし。本文と投稿の雰囲気から、無難に短く褒める。"}
""".strip()

    def _image_note(self, post: XRecentPost) -> str:
        media = [item for item in (post.media or []) if item.get("local_file_path")]
        if not media:
            return ""
        first_path = media[0].get("local_file_path")
        try:
            result = self._text_ai_client.analyze_image(
                first_path,
                prompt=(
                    "日本語で80字以内。XのAIイラスト投稿への返信候補作成に使うため、"
                    "画像の表情、衣装、光、背景、構図、雰囲気を短く具体的に要約してください。"
                ),
                model=None,
            )
            parsed = result.get("parsed_json")
            if isinstance(parsed, dict):
                return self._compact_text(parsed.get("short_description") or parsed.get("label") or result.get("text") or "", limit=180)
            return self._compact_text(result.get("text") or "", limit=180)
        except Exception:
            current_app.logger.exception("Failed to analyze X observation image")
            return ""

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
