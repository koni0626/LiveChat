from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class CinemaNovelReview(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cinema_novel_review"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("cinema_novel.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    feed_post_id = db.Column(db.Integer, db.ForeignKey("feed_post.id"), index=True)
    memory_note_id = db.Column(db.Integer, db.ForeignKey("character_memory_note.id"), index=True)
    review_text = db.Column(db.Text, nullable=False)
    memory_note = db.Column(db.Text)
    rating_label = db.Column(db.String(80))
    status = db.Column(db.String(50), nullable=False, default="published", index=True)
    metadata_json = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint("novel_id", "character_id", "user_id", name="uq_cinema_novel_review_novel_character_user"),
    )
