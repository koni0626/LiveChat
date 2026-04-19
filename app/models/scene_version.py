from ..extensions import db
from .base import CreatedAtMixin


class SceneVersion(db.Model, CreatedAtMixin):
    __tablename__ = "scene_version"

    id = db.Column(db.Integer, primary_key=True)
    scene_id = db.Column(db.Integer, db.ForeignKey("scene.id"), nullable=False)
    version_no = db.Column(db.Integer, nullable=False)
    source_type = db.Column(db.String(50), nullable=False)
    generated_by = db.Column(db.String(100))
    narration_text = db.Column(db.Text)
    dialogue_json = db.Column(db.Text)
    choice_json = db.Column(db.Text)
    scene_state_json = db.Column(db.Text)
    image_prompt_text = db.Column(db.Text)
    note_text = db.Column(db.Text)
    is_adopted = db.Column(db.Integer, nullable=False, default=0)
