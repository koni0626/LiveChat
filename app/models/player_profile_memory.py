from ..extensions import db
from .base import TimestampMixin


class PlayerProfileMemory(db.Model, TimestampMixin):
    __tablename__ = "player_profile_memory"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)
    interest_notes = db.Column(db.Text)
    dislike_notes = db.Column(db.Text)
    conversation_style_notes = db.Column(db.Text)
    humor_notes = db.Column(db.Text)
    romance_notes = db.Column(db.Text)
    goal_notes = db.Column(db.Text)
    frustration_notes = db.Column(db.Text)
    recent_player_notes = db.Column(db.Text)
    profile_json = db.Column(db.Text)
    last_interaction_at = db.Column(db.DateTime)
    memory_enabled = db.Column(db.Boolean, nullable=False, default=True)
