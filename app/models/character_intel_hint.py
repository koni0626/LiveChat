from ..extensions import db
from .base import TimestampMixin


class CharacterIntelHint(db.Model, TimestampMixin):
    __tablename__ = "character_intel_hint"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    target_character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    source_character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    topic = db.Column(db.String(255), nullable=False)
    hint_text = db.Column(db.Text, nullable=False)
    reveal_threshold = db.Column(db.Integer, nullable=False, default=40)
    status = db.Column(db.String(50), nullable=False, default="revealed")
    revealed_at = db.Column(db.DateTime)
    used_at = db.Column(db.DateTime)

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "target_character_id",
            "source_character_id",
            "topic",
            name="uq_character_intel_hint_user_target_source_topic",
        ),
    )
