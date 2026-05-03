from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class WorldLocationServiceItem(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "world_location_service"

    id = db.Column(db.Integer, primary_key=True)
    location_id = db.Column(db.Integer, db.ForeignKey("world_location.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    service_type = db.Column(db.String(100))
    summary = db.Column(db.Text)
    chat_hook = db.Column(db.Text)
    visual_prompt = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False, default="published")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
