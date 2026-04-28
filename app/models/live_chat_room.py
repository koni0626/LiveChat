from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class LiveChatRoom(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "live_chat_room"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    conversation_objective = db.Column(db.Text, nullable=False)
    proxy_player_objective = db.Column(db.Text)
    proxy_player_gender = db.Column(db.String(100))
    proxy_player_speech_style = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False, default="draft", index=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
