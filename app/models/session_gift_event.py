from ..extensions import db
from .base import CreatedAtMixin


class SessionGiftEvent(db.Model, CreatedAtMixin):
    __tablename__ = "session_gift_event"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False, index=True)
    actor_type = db.Column(db.String(50), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    gift_direction = db.Column(db.String(50), nullable=False)
    recognized_label = db.Column(db.String(255))
    recognized_tags_json = db.Column(db.Text)
    reaction_summary = db.Column(db.Text)
    evaluation_delta = db.Column(db.Integer, nullable=False, default=0)
