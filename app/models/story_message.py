from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class StoryMessage(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "story_message"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("story_session.id"), nullable=False, index=True)
    sender_type = db.Column(db.String(50), nullable=False, index=True)
    speaker_name = db.Column(db.String(255))
    message_text = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(50), nullable=False, default="dialogue", index=True)
    order_no = db.Column(db.Integer, nullable=False)
    metadata_json = db.Column(db.Text)
