from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class Project(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "project"

    id = db.Column(db.Integer, primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    thumbnail_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    world_id = db.Column(db.Integer, db.ForeignKey("world.id"))
    title = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(255))
    genre = db.Column(db.String(100), nullable=False)
    summary = db.Column(db.Text)
    play_time_minutes = db.Column(db.Integer)
    project_type = db.Column(db.String(50), nullable=False, default="linear")
    status = db.Column(db.String(50), nullable=False, default="draft")
    visibility = db.Column(db.String(50), nullable=False, default="private")
    chat_enabled = db.Column(db.Integer, nullable=False, default=1)
    settings_json = db.Column(db.Text)
