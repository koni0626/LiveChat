from ..extensions import db
from .base import TimestampMixin


class CharacterUserMemory(db.Model, TimestampMixin):
    __tablename__ = "character_user_memory"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    relationship_summary = db.Column(db.Text)
    memory_notes = db.Column(db.Text)
    preference_notes = db.Column(db.Text)
    unresolved_threads = db.Column(db.Text)
    important_events = db.Column(db.Text)
    affinity_score = db.Column(db.Integer, nullable=False, default=0)
    affinity_label = db.Column(db.String(80))
    affinity_notes = db.Column(db.Text)
    physical_closeness_level = db.Column(db.Integer, nullable=False, default=0)
    last_interaction_at = db.Column(db.DateTime)
    memory_enabled = db.Column(db.Boolean, nullable=False, default=True)

    __table_args__ = (
        db.UniqueConstraint("user_id", "character_id", name="uq_character_user_memory_user_character"),
    )
