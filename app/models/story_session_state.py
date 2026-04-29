from ..extensions import db
from .base import TimestampMixin


class StorySessionState(db.Model, TimestampMixin):
    __tablename__ = "story_session_state"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("story_session.id"), nullable=False, unique=True, index=True)
    state_json = db.Column(db.Text, nullable=False, default="{}")
    version = db.Column(db.Integer, nullable=False, default=1)
