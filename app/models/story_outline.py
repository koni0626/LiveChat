from ..extensions import db
from .base import TimestampMixin


class StoryOutline(db.Model, TimestampMixin):
    __tablename__ = "story_outline"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(
        db.Integer, db.ForeignKey("project.id"), nullable=False, unique=True
    )
    premise = db.Column(db.Text)
    protagonist_name = db.Column(db.String(100))
    protagonist_position = db.Column(db.Text)
    main_goal = db.Column(db.Text)
    branching_policy = db.Column(db.Text)
    ending_policy = db.Column(db.Text)
    outline_text = db.Column(db.Text)
    outline_json = db.Column(db.Text)
