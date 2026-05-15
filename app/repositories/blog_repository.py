from datetime import datetime

from sqlalchemy import or_

from ..extensions import db
from ..models.blog_post import BlogPost


class BlogRepository:
    def list_posts(
        self,
        *,
        project_id: int | None = None,
        character_id: int | None = None,
        statuses: list[str] | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        query = self._post_query(project_id=project_id, character_id=character_id, statuses=statuses, search=search)
        return (
            query.order_by(BlogPost.published_at.desc(), BlogPost.created_at.desc(), BlogPost.id.desc())
            .offset(max(0, int(offset or 0)))
            .limit(max(1, min(int(limit or 50), 100)))
            .all()
        )

    def count_posts(
        self,
        *,
        project_id: int | None = None,
        character_id: int | None = None,
        statuses: list[str] | None = None,
        search: str | None = None,
    ):
        return self._post_query(
            project_id=project_id,
            character_id=character_id,
            statuses=statuses,
            search=search,
        ).count()

    def _post_query(
        self,
        *,
        project_id: int | None = None,
        character_id: int | None = None,
        statuses: list[str] | None = None,
        search: str | None = None,
    ):
        query = BlogPost.query.filter(BlogPost.deleted_at.is_(None))
        if project_id:
            query = query.filter(BlogPost.project_id == project_id)
        if character_id:
            query = query.filter(BlogPost.character_id == character_id)
        if statuses:
            query = query.filter(BlogPost.status.in_(statuses))
        if search:
            keyword = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    BlogPost.theme.ilike(keyword),
                    BlogPost.instruction.ilike(keyword),
                    BlogPost.body.ilike(keyword),
                    BlogPost.status.ilike(keyword),
                )
            )
        return query

    def get_post(self, post_id: int, include_deleted: bool = False):
        query = BlogPost.query.filter(BlogPost.id == post_id)
        if not include_deleted:
            query = query.filter(BlogPost.deleted_at.is_(None))
        return query.first()

    def create_post(self, payload: dict):
        status = payload.get("status") or "draft"
        post = BlogPost(
            project_id=payload["project_id"],
            character_id=payload["character_id"],
            created_by_user_id=payload["created_by_user_id"],
            theme=payload["theme"],
            instruction=payload.get("instruction"),
            body=payload["body"],
            thumbnail_asset_id=payload.get("thumbnail_asset_id"),
            status=status,
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
        for field in ("character_id", "theme", "instruction", "body", "thumbnail_asset_id", "status", "generation_state_json"):
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
