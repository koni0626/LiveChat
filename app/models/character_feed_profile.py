from ..extensions import db
from .base import TimestampMixin


class CharacterFeedProfile(db.Model, TimestampMixin):
    __tablename__ = "character_feed_profile"

    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, unique=True, index=True)
    profile_text = db.Column(db.Text)
    source_post_count = db.Column(db.Integer, nullable=False, default=0)
    source_latest_post_id = db.Column(db.Integer, db.ForeignKey("feed_post.id"))
    summary_state_json = db.Column(db.Text)
