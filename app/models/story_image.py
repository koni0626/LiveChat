from ..extensions import db
from .base import CreatedAtMixin


class StoryImage(db.Model, CreatedAtMixin):
    __tablename__ = "story_image"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("story_session.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False, index=True)
    source_message_id = db.Column(db.Integer, db.ForeignKey("story_message.id"), index=True)
    visual_type = db.Column(db.String(50), nullable=False, default="scene", index=True)
    subject = db.Column(db.String(255))
    prompt_text = db.Column(db.Text)
    reference_asset_ids_json = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
