from ..extensions import db
from .base import TimestampMixin


class GenerationJob(db.Model, TimestampMixin):
    __tablename__ = "generation_job"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    job_type = db.Column(db.String(100), nullable=False)
    target_type = db.Column(db.String(100), nullable=False)
    target_id = db.Column(db.Integer)
    model_name = db.Column(db.String(100))
    request_json = db.Column(db.Text)
    response_json = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False, default="queued")
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
