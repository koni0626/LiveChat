from ..extensions import db
from .base import CreatedAtMixin


class ExportJob(db.Model, CreatedAtMixin):
    __tablename__ = "export_job"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    export_type = db.Column(db.String(100), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    status = db.Column(db.String(50), nullable=False)
    options_json = db.Column(db.Text)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
