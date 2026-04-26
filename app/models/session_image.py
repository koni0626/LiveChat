from ..extensions import db
from .base import CreatedAtMixin


class SessionImage(db.Model, CreatedAtMixin):
    __tablename__ = "session_image"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    owner_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), index=True)
    linked_from_image_id = db.Column(db.Integer, db.ForeignKey("session_image.id"))
    image_type = db.Column(db.String(50), nullable=False)
    prompt_text = db.Column(db.Text)
    state_json = db.Column(db.Text)
    quality = db.Column(db.String(50))
    size = db.Column(db.String(50))
    is_selected = db.Column(db.Integer, nullable=False, default=0)
    is_reference = db.Column(db.Integer, nullable=False, default=0)
