from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class OutingSession(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "outing_session"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey("world_location.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="active", index=True)
    current_step = db.Column(db.Integer, nullable=False, default=0)
    max_steps = db.Column(db.Integer, nullable=False, default=3)
    mood = db.Column(db.String(100))
    summary = db.Column(db.Text)
    memory_title = db.Column(db.String(255))
    memory_summary = db.Column(db.Text)
    state_json = db.Column(db.Text)
    completed_at = db.Column(db.DateTime)
