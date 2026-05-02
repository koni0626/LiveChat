from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class CinemaNovelChapter(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cinema_novel_chapter"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("cinema_novel.id"), nullable=False, index=True)
    chapter_no = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    body_markdown = db.Column(db.Text)
    scene_json = db.Column(db.Text)
    cover_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
