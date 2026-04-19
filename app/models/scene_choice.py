from ..extensions import db
from .base import TimestampMixin


class SceneChoice(db.Model, TimestampMixin):
    __tablename__ = "scene_choice"

    id = db.Column(db.Integer, primary_key=True)
    scene_id = db.Column(db.Integer, db.ForeignKey("scene.id"), nullable=False)
    choice_text = db.Column(db.Text, nullable=False)
    next_scene_id = db.Column(db.Integer, db.ForeignKey("scene.id"))
    condition_json = db.Column(db.Text)
    result_summary = db.Column(db.Text)
    sort_order = db.Column(db.Integer, nullable=False)
