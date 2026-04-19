from ..extensions import db
from .base import TimestampMixin


class World(db.Model, TimestampMixin):
    __tablename__ = "world"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, unique=True)
    name = db.Column(db.String(255), nullable=False)
    era_description = db.Column(db.Text)
    technology_level = db.Column(db.Text)
    social_structure = db.Column(db.Text)
    tone = db.Column(db.Text)
    overview = db.Column(db.Text)
    rules_json = db.Column(db.Text)
    forbidden_json = db.Column(db.Text)
