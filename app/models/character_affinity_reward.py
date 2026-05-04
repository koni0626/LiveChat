from ..extensions import db
from .base import TimestampMixin


class CharacterAffinityReward(db.Model, TimestampMixin):
    __tablename__ = "character_affinity_reward"
    __table_args__ = (
        db.UniqueConstraint("user_id", "character_id", name="uq_character_affinity_reward_user_character"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    event_image_id = db.Column(db.Integer, db.ForeignKey("session_image.id"), nullable=True)
    event_claimed_at = db.Column(db.DateTime)
    costume_ticket_balance = db.Column(db.Integer, nullable=False, default=0)
    costume_ticket_earned_at = db.Column(db.DateTime)
    costume_ticket_used_at = db.Column(db.DateTime)
    lccd_unlocked_session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=True, index=True)
    saved_outfit_id = db.Column(db.Integer, db.ForeignKey("character_outfit.id"), nullable=True)
