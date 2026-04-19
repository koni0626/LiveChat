from ..extensions import db
from .base import CreatedAtMixin


class UsageLog(db.Model, CreatedAtMixin):
    __tablename__ = "usage_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"))
    action_type = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit = db.Column(db.String(50))
    detail_json = db.Column(db.Text)
