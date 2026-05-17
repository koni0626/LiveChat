from __future__ import annotations

from typing import Any
from types import SimpleNamespace

from ..extensions import db
from ..models.x_observation_reply import XObservationReply
from ..utils import json_util


class XObservationReplyService:
    def latest_by_tweet_ids(self, project_id: int, tweet_ids: list[str]) -> dict[str, dict[str, Any]]:
        ids = [str(tweet_id) for tweet_id in tweet_ids if tweet_id]
        if not ids:
            return {}
        rows = (
            XObservationReply.query.filter(
                XObservationReply.project_id == project_id,
                XObservationReply.target_tweet_id.in_(ids),
            )
            .order_by(XObservationReply.created_at.desc(), XObservationReply.id.desc())
            .all()
        )
        replies = {}
        for row in rows:
            replies.setdefault(row.target_tweet_id, self.serialize(row))
        return replies

    def latest_by_tweet_id(self, project_id: int, tweet_id: str) -> dict[str, Any] | None:
        row = (
            XObservationReply.query.filter_by(project_id=project_id, target_tweet_id=str(tweet_id))
            .order_by(XObservationReply.created_at.desc(), XObservationReply.id.desc())
            .first()
        )
        return self.serialize(row) if row else None

    def create(
        self,
        *,
        project_id: int,
        tweet,
        reply_text: str,
        published: dict[str, Any],
        replied_by_user_id: int,
        character_id: int | None = None,
    ) -> XObservationReply:
        row = XObservationReply(
            project_id=project_id,
            target_tweet_id=str(tweet.id),
            target_author_id=str(tweet.author_id or ""),
            target_author_name=tweet.author_name,
            target_author_username=tweet.author_username,
            character_id=character_id,
            replied_by_user_id=replied_by_user_id,
            reply_text=reply_text,
            reply_x_post_id=published.get("x_post_id") or None,
            reply_url=published.get("url") or None,
            metadata_json=json_util.dumps({"published": published}),
        )
        db.session.add(row)
        db.session.commit()
        return row

    def create_from_target_data(
        self,
        *,
        project_id: int,
        target: dict[str, Any],
        tweet_id: str,
        reply_text: str,
        published: dict[str, Any],
        replied_by_user_id: int,
        character_id: int | None = None,
    ) -> XObservationReply:
        return self.create(
            project_id=project_id,
            tweet=SimpleNamespace(
                id=str(tweet_id),
                author_id=target.get("author_id") or "",
                author_name=target.get("author_name") or "",
                author_username=target.get("author_username") or "",
            ),
            reply_text=reply_text,
            published=published,
            replied_by_user_id=replied_by_user_id,
            character_id=character_id,
        )

    def apply_to_posts(self, project_id: int, posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        replies = self.latest_by_tweet_ids(project_id, [post.get("id") for post in posts])
        for post in posts:
            reply = replies.get(str(post.get("id") or ""))
            post["observation_reply"] = reply
            post["is_replied"] = bool(reply)
        return posts

    def serialize(self, row: XObservationReply) -> dict[str, Any]:
        return {
            "id": row.id,
            "target_tweet_id": row.target_tweet_id,
            "target_author_id": row.target_author_id,
            "target_author_name": row.target_author_name,
            "target_author_username": row.target_author_username,
            "character_id": row.character_id,
            "reply_text": row.reply_text,
            "reply_x_post_id": row.reply_x_post_id,
            "reply_url": row.reply_url,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
