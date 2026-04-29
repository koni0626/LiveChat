from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class WorldMapImage(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "world_map_image"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    prompt_text = db.Column(db.Text)
    source_type = db.Column(db.String(50), nullable=False, default="upload")
    quality = db.Column(db.String(50))
    size = db.Column(db.String(50))
    is_active = db.Column(db.Integer, nullable=False, default=0)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
