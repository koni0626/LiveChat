from ..extensions import db
from .base import TimestampMixin


class ChatSessionObjectiveNote(db.Model, TimestampMixin):
    __tablename__ = "chat_session_objective_note"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=True, index=True)
    title = db.Column(db.String(160), nullable=False)
    note = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Integer, nullable=False, default=3)
    status = db.Column(db.String(50), nullable=False, default="active", index=True)
    source_type = db.Column(db.String(50), nullable=False, default="direction_ai")
    source_ref = db.Column(db.String(255))
    confidence = db.Column(db.Float, nullable=False, default=1.0)
