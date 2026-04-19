from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class Scene(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "scene"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"), nullable=False)
    parent_scene_id = db.Column(db.Integer, db.ForeignKey("scene.id"))
    scene_key = db.Column(db.String(255))
    title = db.Column(db.String(255))
    summary = db.Column(db.Text)
    narration_text = db.Column(db.Text)
    dialogue_json = db.Column(db.Text)
    scene_state_json = db.Column(db.Text)
    image_prompt_text = db.Column(db.Text)
    active_version_id = db.Column(db.Integer, db.ForeignKey("scene_version.id"))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    is_fixed = db.Column(db.Integer, nullable=False, default=0)
