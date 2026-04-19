from ..extensions import db
from .base import TimestampMixin


class CharacterImageRule(db.Model, TimestampMixin):
    __tablename__ = "character_image_rule"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, unique=True)
    hair_rule = db.Column(db.Text)
    face_rule = db.Column(db.Text)
    ear_rule = db.Column(db.Text)
    accessory_rule = db.Column(db.Text)
    outfit_rule = db.Column(db.Text)
    style_rule = db.Column(db.Text)
    negative_rule = db.Column(db.Text)
    default_quality = db.Column(db.String(50), nullable=False, default="low")
    default_size = db.Column(db.String(50), nullable=False, default="1024x1024")
    prompt_prefix = db.Column(db.Text)
    prompt_suffix = db.Column(db.Text)
