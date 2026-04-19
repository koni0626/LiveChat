from ..extensions import db
from .base import CreatedAtMixin


class SceneCharacter(db.Model, CreatedAtMixin):
    __tablename__ = "scene_character"

    id = db.Column(db.Integer, primary_key=True)
    scene_id = db.Column(db.Integer, db.ForeignKey("scene.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
