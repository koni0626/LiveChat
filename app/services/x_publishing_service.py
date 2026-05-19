from __future__ import annotations

import os
import re
import unicodedata

from flask import current_app


class XPublishingService:
    TWEET_WEIGHT_LIMIT = 280
    THREAD_MARKER_RESERVE = 12

    def __init__(self, asset_service=None):
        self._asset_service = asset_service

    def is_configured(self) -> bool:
        return all(
            current_app.config.get(key)
            for key in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")
        )

    def publish_feed_post(self, post, image_asset=None) -> dict:
        if not self.is_configured():
            raise RuntimeError("X API keys are not configured")
        try:
            import tweepy
        except ImportError as exc:
            raise RuntimeError("tweepy is required for X publishing. Run pip install -r requirements.txt") from exc

        api_key = current_app.config["X_API_KEY"]
        api_secret = current_app.config["X_API_SECRET"]
        access_token = current_app.config["X_ACCESS_TOKEN"]
        access_token_secret = current_app.config["X_ACCESS_TOKEN_SECRET"]
        bearer_token = current_app.config.get("X_BEARER_TOKEN") or None

        media_ids = []
        if image_asset and getattr(image_asset, "file_path", None) and os.path.exists(image_asset.file_path):
            auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
            media_api = tweepy.API(auth)
            media = media_api.media_upload(filename=image_asset.file_path)
            media_ids.append(str(media.media_id))

        client = tweepy.Client(
            bearer_token=bearer_token,
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        responses = self._create_thread(client, [{"text": post.body, "media_ids": media_ids}])
        data = responses[0] if responses else {}
        return {
            "x_post_id": str(data.get("id") or ""),
            "response": data,
            "posts": responses,
            "thread_count": len(responses),
            "media_ids": media_ids,
        }

    def publish_thread_posts(self, posts: list[dict]) -> dict:
        if not self.is_configured():
            raise RuntimeError("X API keys are not configured")
        try:
            import tweepy
        except ImportError as exc:
            raise RuntimeError("tweepy is required for X publishing. Run pip install -r requirements.txt") from exc

        api_key = current_app.config["X_API_KEY"]
        api_secret = current_app.config["X_API_SECRET"]
        access_token = current_app.config["X_ACCESS_TOKEN"]
        access_token_secret = current_app.config["X_ACCESS_TOKEN_SECRET"]
        bearer_token = current_app.config.get("X_BEARER_TOKEN") or None

        client = tweepy.Client(
            bearer_token=bearer_token,
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_token_secret,
        )
        responses = self._create_thread(client, posts)
        first = responses[0] if responses else {}
        return {
            "x_post_id": str(first.get("id") or ""),
            "response": first,
            "posts": responses,
            "thread_count": len(responses),
        }

    def publish_reply(self, tweet_id: str, text: str) -> dict:
        normalized = self._normalize_text(text)
        if not normalized:
            raise ValueError("reply text is required")
        if self._tweet_weight(normalized) > self.TWEET_WEIGHT_LIMIT:
            raise ValueError("reply text is too long for X")
        if not self.is_configured():
            raise RuntimeError("X API keys are not configured")
        try:
            import tweepy
        except ImportError as exc:
            raise RuntimeError("tweepy is required for X publishing. Run pip install -r requirements.txt") from exc

        client = tweepy.Client(
            bearer_token=current_app.config.get("X_BEARER_TOKEN") or None,
            consumer_key=current_app.config["X_API_KEY"],
            consumer_secret=current_app.config["X_API_SECRET"],
            access_token=current_app.config["X_ACCESS_TOKEN"],
            access_token_secret=current_app.config["X_ACCESS_TOKEN_SECRET"],
        )
        try:
            response = client.create_tweet(text=normalized, in_reply_to_tweet_id=str(tweet_id))
        except Exception as exc:
            raise RuntimeError(self._friendly_tweepy_error(exc)) from exc
        data = getattr(response, "data", None) or {}
        x_post_id = str(data.get("id") or "")
        return {
            "x_post_id": x_post_id,
            "in_reply_to_tweet_id": str(tweet_id),
            "text": normalized,
            "url": f"https://x.com/i/web/status/{x_post_id}" if x_post_id else "",
            "response": data,
        }

    def upload_media_paths(self, image_paths: list[str]) -> dict[str, str]:
        if not self.is_configured():
            raise RuntimeError("X API keys are not configured")
        try:
            import tweepy
        except ImportError as exc:
            raise RuntimeError("tweepy is required for X publishing. Run pip install -r requirements.txt") from exc

        api_key = current_app.config["X_API_KEY"]
        api_secret = current_app.config["X_API_SECRET"]
        access_token = current_app.config["X_ACCESS_TOKEN"]
        access_token_secret = current_app.config["X_ACCESS_TOKEN_SECRET"]

        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
        media_api = tweepy.API(auth)
        uploaded = {}
        for image_path in image_paths:
            normalized = os.path.abspath(str(image_path))
            if not os.path.exists(normalized):
                raise FileNotFoundError(f"image file not found: {normalized}")
            media = media_api.media_upload(filename=normalized)
            uploaded[normalized] = str(media.media_id)
        return uploaded

    def _create_thread(self, client, posts: list[dict]) -> list[dict]:
        responses = []
        previous_post_id = None
        for post in posts:
            text = str(post.get("text") or "")
            media_ids = [str(media_id) for media_id in post.get("media_ids") or [] if media_id]
            parts = self.split_thread(text)
            for index, part in enumerate(parts):
                kwargs = {"text": part}
                if index == 0 and media_ids:
                    kwargs["media_ids"] = media_ids
                if previous_post_id:
                    kwargs["in_reply_to_tweet_id"] = previous_post_id
                response = client.create_tweet(**kwargs)
                data = getattr(response, "data", None) or {}
                responses.append(data)
                previous_post_id = str(data.get("id") or "") or previous_post_id
        return responses

    def split_thread(self, text: str) -> list[str]:
        normalized = self._normalize_text(text)
        if not normalized:
            return [""]
        if self._tweet_weight(normalized) <= self.TWEET_WEIGHT_LIMIT:
            return [normalized]

        raw_parts = self._split_by_weight(normalized, self.TWEET_WEIGHT_LIMIT - self.THREAD_MARKER_RESERVE)
        if len(raw_parts) <= 1:
            return raw_parts

        width = len(str(len(raw_parts)))
        marker_cost = len(f" ({'0' * width}/{'0' * width})")
        body_limit = self.TWEET_WEIGHT_LIMIT - marker_cost
        raw_parts = self._split_by_weight(normalized, body_limit)
        width = len(str(len(raw_parts)))
        return [f"{part} ({index}/{len(raw_parts)})" for index, part in enumerate(raw_parts, start=1)]

    def _split_by_weight(self, text: str, limit: int) -> list[str]:
        chunks = self._preferred_chunks(text)
        parts: list[str] = []
        current = ""
        for chunk in chunks:
            candidate = self._join_chunks(current, chunk)
            if candidate and self._tweet_weight(candidate) <= limit:
                current = candidate
                continue
            if current:
                parts.append(current)
                current = ""
            if self._tweet_weight(chunk) <= limit:
                current = chunk
                continue
            hard_parts = self._hard_split(chunk, limit)
            parts.extend(hard_parts[:-1])
            current = hard_parts[-1] if hard_parts else ""
        if current:
            parts.append(current)
        return [part for part in parts if part]

    def _preferred_chunks(self, text: str) -> list[str]:
        chunks: list[str] = []
        paragraphs = re.split(r"\n{2,}", text)
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            sentences = re.findall(r".+?(?:[。！？!?]+|$)", paragraph, flags=re.S)
            for sentence in sentences:
                cleaned = sentence.strip()
                if cleaned:
                    chunks.append(cleaned)
        return chunks or [text]

    def _join_chunks(self, current: str, chunk: str) -> str:
        if not current:
            return chunk
        separator = "\n\n" if "\n" in current or "\n" in chunk else "\n"
        return f"{current}{separator}{chunk}"

    def _hard_split(self, text: str, limit: int) -> list[str]:
        parts: list[str] = []
        current = ""
        for char in text:
            candidate = current + char
            if current and self._tweet_weight(candidate) > limit:
                parts.append(current.rstrip())
                current = char
            else:
                current = candidate
        if current.strip():
            parts.append(current.strip())
        return parts

    def _normalize_text(self, text: str) -> str:
        normalized = unicodedata.normalize("NFC", str(text or "")).strip()
        normalized = re.sub(r"[ \t]+\n", "\n", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized

    def _tweet_weight(self, text: str) -> int:
        weight = 0
        position = 0
        for match in re.finditer(r"https?://\S+", text):
            weight += self._text_weight(text[position : match.start()])
            weight += 23
            position = match.end()
        weight += self._text_weight(text[position:])
        return weight

    def _text_weight(self, text: str) -> int:
        total = 0
        for char in text:
            if char in "\u200d\ufe0e\ufe0f":
                continue
            total += 2 if self._is_double_weight(char) else 1
        return total

    def _is_double_weight(self, char: str) -> bool:
        codepoint = ord(char)
        if codepoint >= 0x1100:
            return True
        return unicodedata.east_asian_width(char) in {"W", "F"}

    def _friendly_tweepy_error(self, error: Exception) -> str:
        api_messages = []
        for attr in ("api_messages", "errors"):
            value = getattr(error, attr, None)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        api_messages.append(str(item.get("message") or item.get("detail") or item))
                    elif item:
                        api_messages.append(str(item))
        response_text = getattr(getattr(error, "response", None), "text", None)
        parts = [message for message in api_messages if message]
        if response_text:
            parts.append(str(response_text))
        if parts:
            return "X reply failed: " + " / ".join(parts)
        return f"X reply failed: {error}"
