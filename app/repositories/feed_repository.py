from datetime import datetime

from sqlalchemy import func, or_

from ..extensions import db
from ..models.character import Character
from ..models.character_feed_profile import CharacterFeedProfile
from ..models.feed_like import FeedLike
from ..models.feed_post import FeedPost
from ..models.project import Project


class FeedRepository:
    def list_posts(
        self,
        *,
        project_id: int | None = None,
        character_id: int | None = None,
        statuses: list[str] | None = None,
        search: str | None = None,
        limit: int = 50,
    ):
        query = FeedPost.query.filter(FeedPost.deleted_at.is_(None))
        if project_id:
            query = query.filter(FeedPost.project_id == project_id)
        if character_id:
            query = query.filter(FeedPost.character_id == character_id)
        if statuses:
            query = query.filter(FeedPost.status.in_(statuses))
        if search:
            keyword = f"%{search.strip()}%"
            query = query.filter(or_(FeedPost.body.ilike(keyword), FeedPost.status.ilike(keyword)))
        return (
            query.order_by(FeedPost.published_at.desc(), FeedPost.created_at.desc(), FeedPost.id.desc())
            .limit(max(1, min(int(limit or 50), 100)))
            .all()
        )

    def get_post(self, post_id: int, include_deleted: bool = False):
        query = FeedPost.query.filter(FeedPost.id == post_id)
        if not include_deleted:
            query = query.filter(FeedPost.deleted_at.is_(None))
        return query.first()

    def character_post_ranking(self, *, limit: int = 10, project_id: int | None = None, published_only: bool = True):
        query = (
            db.session.query(
                Character,
                Project,
                func.count(FeedPost.id).label("post_count"),
            )
            .join(FeedPost, FeedPost.character_id == Character.id)
            .join(Project, Project.id == FeedPost.project_id)
            .filter(
                FeedPost.deleted_at.is_(None),
                Character.deleted_at.is_(None),
                Project.deleted_at.is_(None),
            )
        )
        if published_only:
            query = query.filter(FeedPost.status == "published")
        if project_id:
            query = query.filter(FeedPost.project_id == project_id)
        return (
            query.group_by(Character.id, Project.id)
            .order_by(func.count(FeedPost.id).desc(), Character.id.asc())
            .limit(max(1, min(int(limit or 10), 50)))
            .all()
        )

    def create_post(self, payload: dict):
        status = payload.get("status") or "draft"
        post = FeedPost(
            project_id=payload["project_id"],
            character_id=payload["character_id"],
            created_by_user_id=payload["created_by_user_id"],
            body=payload["body"],
            image_asset_id=payload.get("image_asset_id"),
            status=status,
            like_count=0,
            generation_state_json=payload.get("generation_state_json"),
            published_at=datetime.utcnow() if status == "published" else None,
        )
        db.session.add(post)
        db.session.commit()
        return post

    def update_post(self, post_id: int, payload: dict):
        post = self.get_post(post_id, include_deleted=True)
        if not post or post.deleted_at is not None:
            return None
        previous_status = post.status
        for field in ("character_id", "body", "image_asset_id", "status", "generation_state_json"):
            if field in payload:
                setattr(post, field, payload[field])
        if previous_status != "published" and post.status == "published":
            post.published_at = datetime.utcnow()
        if post.status != "published":
            post.published_at = None
        db.session.commit()
        return post

    def delete_post(self, post_id: int):
        post = self.get_post(post_id, include_deleted=True)
        if not post:
            return False
        if post.deleted_at is None:
            post.deleted_at = datetime.utcnow()
            db.session.commit()
        return True

    def get_like(self, post_id: int, user_id: int):
        return FeedLike.query.filter(FeedLike.feed_post_id == post_id, FeedLike.user_id == user_id).first()

    def liked_post_ids(self, post_ids: list[int], user_id: int):
        if not post_ids:
            return set()
        rows = FeedLike.query.filter(
            FeedLike.feed_post_id.in_(post_ids),
            FeedLike.user_id == user_id,
            FeedLike.deleted_at.is_(None),
        ).all()
        return {row.feed_post_id for row in rows}

    def set_like(self, post_id: int, user_id: int, liked: bool):
        post = self.get_post(post_id)
        if not post:
            return None
        row = self.get_like(post_id, user_id)
        changed = False
        if liked:
            if row is None:
                row = FeedLike(feed_post_id=post_id, user_id=user_id)
                db.session.add(row)
                changed = True
            elif row.deleted_at is not None:
                row.deleted_at = None
                changed = True
        elif row is not None and row.deleted_at is None:
            row.deleted_at = datetime.utcnow()
            changed = True
        if changed:
            post.like_count = max(
                0,
                FeedLike.query.filter(FeedLike.feed_post_id == post_id, FeedLike.deleted_at.is_(None)).count()
            )
            db.session.commit()
        return post

    def get_profile(self, character_id: int):
        return CharacterFeedProfile.query.filter(CharacterFeedProfile.character_id == character_id).first()

    def upsert_profile(self, character_id: int, payload: dict):
        row = self.get_profile(character_id)
        if row is None:
            row = CharacterFeedProfile(character_id=character_id)
            db.session.add(row)
        row.profile_text = payload.get("profile_text")
        row.source_post_count = payload.get("source_post_count") or 0
        row.source_latest_post_id = payload.get("source_latest_post_id")
        row.summary_state_json = payload.get("summary_state_json")
        db.session.commit()
        return row
