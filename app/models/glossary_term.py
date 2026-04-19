from ..extensions import db
from .base import TimestampMixin


class GlossaryTerm(db.Model, TimestampMixin):
    __tablename__ = "glossary_term"

    id = db.Column(db.Integer, primary_key=True)
    world_id = db.Column(db.Integer, db.ForeignKey("world.id"), nullable=False)
    term = db.Column(db.String(255), nullable=False)
    reading = db.Column(db.String(255))
    description = db.Column(db.Text)
    category = db.Column(db.String(100))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
