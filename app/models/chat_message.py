from ..extensions import db
from .base import CreatedAtMixin


class ChatMessage(db.Model, CreatedAtMixin):
    __tablename__ = "chat_message"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False, index=True)
    sender_type = db.Column(db.String(50), nullable=False)
    speaker_name = db.Column(db.String(255))
    message_text = db.Column(db.Text, nullable=False)
    order_no = db.Column(db.Integer, nullable=False)
    message_role = db.Column(db.String(50))
    state_snapshot_json = db.Column(db.Text)
