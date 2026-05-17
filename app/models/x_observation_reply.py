from ..extensions import db
from .base import TimestampMixin


class XObservationReply(db.Model, TimestampMixin):
    __tablename__ = "x_observation_reply"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    target_tweet_id = db.Column(db.String(100), nullable=False, index=True)
    target_author_id = db.Column(db.String(100), index=True)
    target_author_name = db.Column(db.String(255))
    target_author_username = db.Column(db.String(255), index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), index=True)
    replied_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    reply_text = db.Column(db.Text, nullable=False)
    reply_x_post_id = db.Column(db.String(100), index=True)
    reply_url = db.Column(db.String(512))
    metadata_json = db.Column(db.Text)
