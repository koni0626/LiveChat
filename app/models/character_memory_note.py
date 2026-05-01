from ..extensions import db
from .base import TimestampMixin


class CharacterMemoryNote(db.Model, TimestampMixin):
    __tablename__ = "character_memory_note"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False, default="other")
    note = db.Column(db.Text, nullable=False)
    source_type = db.Column(db.String(50), nullable=False, default="manual")
    source_ref = db.Column(db.String(255))
    confidence = db.Column(db.Float, nullable=False, default=1.0)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    pinned = db.Column(db.Boolean, nullable=False, default=False)
