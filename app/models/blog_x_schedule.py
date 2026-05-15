from ..extensions import db
from .base import TimestampMixin


class BlogXSchedule(db.Model, TimestampMixin):
    __tablename__ = "blog_x_schedule"

    id = db.Column(db.Integer, primary_key=True)
    blog_post_id = db.Column(db.Integer, db.ForeignKey("blog_post.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default="scheduled", index=True)
    x_post_id = db.Column(db.String(100))
    error_message = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    posted_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)
