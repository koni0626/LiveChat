from ..extensions import db
from .base import TimestampMixin


class Chapter(db.Model, TimestampMixin):
    __tablename__ = "chapter"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    chapter_no = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    summary = db.Column(db.Text)
    objective = db.Column(db.Text)
    sort_order = db.Column(db.Integer, nullable=False)
