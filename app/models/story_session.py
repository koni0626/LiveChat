from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class StorySession(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "story_session"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    story_id = db.Column(db.Integer, db.ForeignKey("story.id"), nullable=False, index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(255))
    status = db.Column(db.String(50), nullable=False, default="active", index=True)
    privacy_status = db.Column(db.String(50), nullable=False, default="private", index=True)
    player_name = db.Column(db.String(100))
    active_image_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    story_snapshot_json = db.Column(db.Text)
    settings_json = db.Column(db.Text)
