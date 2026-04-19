from ..extensions import db
from .base import CreatedAtMixin


class GeneratedCandidate(db.Model, CreatedAtMixin):
    __tablename__ = "generated_candidate"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    target_type = db.Column(db.String(100), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    candidate_type = db.Column(db.String(100), nullable=False)
    content_text = db.Column(db.Text)
    content_json = db.Column(db.Text)
    score = db.Column(db.Float)
    tags_json = db.Column(db.Text)
    is_selected = db.Column(db.Integer, nullable=False, default=0)
