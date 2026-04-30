from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class CharacterOutfit(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "character_outfit"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False, index=True)
    thumbnail_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), index=True)
    source_type = db.Column(db.String(50), nullable=False, default="outfit", index=True)
    tags_json = db.Column(db.Text)
    usage_scene = db.Column(db.String(80), index=True)
    season = db.Column(db.String(80), index=True)
    mood = db.Column(db.String(80), index=True)
    color_notes = db.Column(db.Text)
    fixed_parts = db.Column(db.Text)
    allowed_changes = db.Column(db.Text)
    ng_rules = db.Column(db.Text)
    prompt_notes = db.Column(db.Text)
    is_default = db.Column(db.Boolean, nullable=False, default=False, index=True)
    status = db.Column(db.String(50), nullable=False, default="active", index=True)
