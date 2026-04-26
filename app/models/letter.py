from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class Letter(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "letter"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    room_id = db.Column(db.Integer, db.ForeignKey("live_chat_room.id"), index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), index=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    sender_character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    subject = db.Column(db.String(255), nullable=False)
    body = db.Column(db.Text, nullable=False)
    summary = db.Column(db.Text)
    image_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    status = db.Column(db.String(50), nullable=False, default="unread", index=True)
    trigger_type = db.Column(db.String(50))
    trigger_reason = db.Column(db.Text)
    generation_state_json = db.Column(db.Text)
    read_at = db.Column(db.DateTime)
