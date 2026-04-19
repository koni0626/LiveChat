from ..extensions import db
from .base import TimestampMixin


class StoryMemory(db.Model, TimestampMixin):
    __tablename__ = "story_memory"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False)
    chapter_id = db.Column(db.Integer, db.ForeignKey("chapter.id"))
    scene_id = db.Column(db.Integer, db.ForeignKey("scene.id"))
    memory_type = db.Column(db.String(50), nullable=False)
    memory_key = db.Column(db.String(100), nullable=False)
    content_text = db.Column(db.Text, nullable=False)
    detail_json = db.Column(db.Text)
    importance = db.Column(db.Integer, nullable=False, default=0)
