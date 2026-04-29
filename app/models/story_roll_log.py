from ..extensions import db
from .base import CreatedAtMixin


class StoryRollLog(db.Model, CreatedAtMixin):
    __tablename__ = "story_roll_log"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("story_session.id"), nullable=False, index=True)
    message_id = db.Column(db.Integer, db.ForeignKey("story_message.id"), index=True)
    formula = db.Column(db.String(100), nullable=False)
    dice_json = db.Column(db.Text, nullable=False)
    modifier = db.Column(db.Integer, nullable=False, default=0)
    total = db.Column(db.Integer, nullable=False)
    target = db.Column(db.Integer)
    outcome = db.Column(db.String(50))
    reason = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
