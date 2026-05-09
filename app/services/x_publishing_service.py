from __future__ import annotations

import os

from flask import current_app


class XPublishingService:
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
        kwargs = {"text": post.body[:280]}
        if media_ids:
            kwargs["media_ids"] = media_ids
        response = client.create_tweet(**kwargs)
        data = getattr(response, "data", None) or {}
        return {
            "x_post_id": str(data.get("id") or ""),
            "response": data,
            "media_ids": media_ids,
        }
