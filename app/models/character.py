from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class Character(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "character"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    nickname = db.Column(db.String(100))
    gender = db.Column(db.String(100))
    age_impression = db.Column(db.String(100))
    first_person = db.Column(db.String(100))
    second_person = db.Column(db.String(100))
    personality = db.Column(db.Text)
    speech_style = db.Column(db.Text)
    speech_sample = db.Column(db.Text)
    ng_rules = db.Column(db.Text)
    appearance_summary = db.Column(db.Text)
    memory_notes = db.Column(db.Text)
    favorite_items_json = db.Column(db.Text)
    memory_profile_json = db.Column(db.Text)
    base_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    thumbnail_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
