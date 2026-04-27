from ..extensions import db
from .base import CreatedAtMixin, SoftDeleteMixin


class FeedLike(db.Model, CreatedAtMixin, SoftDeleteMixin):
    __tablename__ = "feed_like"

    id = db.Column(db.Integer, primary_key=True)
    feed_post_id = db.Column(db.Integer, db.ForeignKey("feed_post.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)

    __table_args__ = (
        db.UniqueConstraint("feed_post_id", "user_id", name="uq_feed_like_post_user"),
    )
