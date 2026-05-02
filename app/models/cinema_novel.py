from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class CinemaNovel(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cinema_novel"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    subtitle = db.Column(db.String(255))
    description = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False, default="draft", index=True)
    mode = db.Column(db.String(80), nullable=False, default="cinema_novel", index=True)
    cover_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    poster_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    source_path = db.Column(db.String(512))
    production_json = db.Column(db.Text)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
