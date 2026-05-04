from ..extensions import db
from .base import TimestampMixin


class SessionCharacterAffinity(db.Model, TimestampMixin):
    __tablename__ = "session_character_affinity"
    __table_args__ = (
        db.UniqueConstraint("session_id", "character_id", name="uq_session_character_affinity_session_character"),
    )

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    affinity_score = db.Column(db.Integer, nullable=False, default=0)
    affinity_label = db.Column(db.String(80))
    affinity_notes = db.Column(db.Text)
    physical_closeness_level = db.Column(db.Integer, nullable=False, default=0)
    locked_at_100 = db.Column(db.Boolean, nullable=False, default=False)
    reached_100_at = db.Column(db.DateTime)
    last_interaction_at = db.Column(db.DateTime)
