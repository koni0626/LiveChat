from ..extensions import db
from .base import TimestampMixin


class EndingCondition(db.Model, TimestampMixin):
    __tablename__ = "ending_condition"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    ending_type = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    condition_text = db.Column(db.Text)
    condition_json = db.Column(db.Text)
    priority = db.Column(db.Integer, nullable=False, default=0)
