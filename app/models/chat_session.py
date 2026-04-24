from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class ChatSession(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "chat_session"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    title = db.Column(db.String(255))
    session_type = db.Column(db.String(50), nullable=False, default="live_chat")
    status = db.Column(db.String(50), nullable=False, default="active")
    active_image_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    player_name = db.Column(db.String(100))
    settings_json = db.Column(db.Text)
