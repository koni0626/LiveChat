from ..extensions import db
from .base import CreatedAtMixin


class SessionCharacter(db.Model, CreatedAtMixin):
    __tablename__ = "session_character"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    role_type = db.Column(db.String(50), nullable=False, default="main")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
