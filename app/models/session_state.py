from ..extensions import db
from .base import TimestampMixin


class SessionState(db.Model, TimestampMixin):
    __tablename__ = "session_state"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False, unique=True, index=True)
    state_json = db.Column(db.Text, nullable=False, default="{}")
    narration_note = db.Column(db.Text)
    visual_prompt_text = db.Column(db.Text)
