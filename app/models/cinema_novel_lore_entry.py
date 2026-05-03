from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class CinemaNovelLoreEntry(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cinema_novel_lore_entry"

    id = db.Column(db.Integer, primary_key=True)
    novel_id = db.Column(db.Integer, db.ForeignKey("cinema_novel.id"), nullable=False, index=True)
    lore_type = db.Column(db.String(50), nullable=False, default="other", index=True)
    name = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text, nullable=False)
    role_note = db.Column(db.Text)
    source_note = db.Column(db.Text)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    metadata_json = db.Column(db.Text)

    __table_args__ = (
        db.UniqueConstraint("novel_id", "lore_type", "name", name="uq_cinema_novel_lore_entry_novel_type_name"),
    )
