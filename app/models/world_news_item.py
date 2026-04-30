from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class WorldNewsItem(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "world_news_item"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    related_character_id = db.Column(db.Integer, db.ForeignKey("character.id"), index=True)
    related_location_id = db.Column(db.Integer, db.ForeignKey("world_location.id"), index=True)
    news_type = db.Column(db.String(80), nullable=False, default="location_news", index=True)
    title = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    importance = db.Column(db.Integer, nullable=False, default=3)
    source_type = db.Column(db.String(80), nullable=False, default="manual_ai", index=True)
    source_ref_type = db.Column(db.String(80))
    source_ref_id = db.Column(db.Integer)
    return_url = db.Column(db.String(512))
    status = db.Column(db.String(50), nullable=False, default="published", index=True)
    metadata_json = db.Column(db.Text)
