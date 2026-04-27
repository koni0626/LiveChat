from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class FeedPost(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "feed_post"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    image_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    status = db.Column(db.String(50), nullable=False, default="draft", index=True)
    like_count = db.Column(db.Integer, nullable=False, default=0)
    generation_state_json = db.Column(db.Text)
    published_at = db.Column(db.DateTime)
