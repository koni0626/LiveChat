from ..extensions import db
from .base import CreatedAtMixin


class SceneImage(db.Model, CreatedAtMixin):
    __tablename__ = "scene_image"

    id = db.Column(db.Integer, primary_key=True)
    scene_id = db.Column(db.Integer, db.ForeignKey("scene.id"), nullable=False)
    scene_version_id = db.Column(db.Integer, db.ForeignKey("scene_version.id"))
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    image_type = db.Column(db.String(50), nullable=False)
    generation_job_id = db.Column(db.Integer, db.ForeignKey("generation_job.id"))
    prompt_text = db.Column(db.Text)
    state_json = db.Column(db.Text)
    quality = db.Column(db.String(50), nullable=False)
    size = db.Column(db.String(50), nullable=False)
    is_selected = db.Column(db.Integer, nullable=False, default=0)
