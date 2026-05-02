from ..extensions import db
from .base import TimestampMixin


class CharacterMemorySummary(db.Model, TimestampMixin):
    __tablename__ = "character_memory_summary"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    summary_json = db.Column(db.Text)
    prompt_text = db.Column(db.Text)
    source_note_count = db.Column(db.Integer, nullable=False, default=0)
    source_note_max_id = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "character_id", name="uq_character_memory_summary_user_character"),
    )
