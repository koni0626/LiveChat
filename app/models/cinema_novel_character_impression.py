from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class CinemaNovelCharacterImpression(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cinema_novel_character_impression"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("cinema_novel.id"), nullable=False, index=True)
    reviewer_character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    target_name = db.Column(db.String(255), nullable=False)
    target_character_id = db.Column(db.Integer, db.ForeignKey("character.id"), index=True)
    impression_text = db.Column(db.Text, nullable=False)
    talk_hint = db.Column(db.Text)
    memory_note_id = db.Column(db.Integer, db.ForeignKey("character_memory_note.id"), index=True)
    metadata_json = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint(
            "novel_id",
            "reviewer_character_id",
            "user_id",
            "target_name",
            name="uq_cinema_novel_character_impression_unique_target",
        ),
    )
