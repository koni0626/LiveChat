from ..extensions import db
from .base import TimestampMixin


class CinemaNovelProgress(db.Model, TimestampMixin):
    __tablename__ = "cinema_novel_progress"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("cinema_novel.id"), nullable=False, index=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey("cinema_novel_chapter.id"), nullable=False, index=True)
    scene_index = db.Column(db.Integer, nullable=False, default=0)
    page_index = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint("user_id", "novel_id", name="uq_cinema_novel_progress_user_novel"),
    )
