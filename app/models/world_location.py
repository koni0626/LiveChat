from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class WorldLocation(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "world_location"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    region = db.Column(db.String(100))
    location_type = db.Column(db.String(100))
    tags_json = db.Column(db.Text)
    description = db.Column(db.Text)
    image_prompt = db.Column(db.Text)
    owner_character_id = db.Column(db.Integer, db.ForeignKey("character.id"), index=True)
    image_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    source_type = db.Column(db.String(50), nullable=False, default="manual")
    source_note = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False, default="published")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
