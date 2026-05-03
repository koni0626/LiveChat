from ..extensions import db
from .base import TimestampMixin


class InventoryItem(db.Model, TimestampMixin):
    __tablename__ = "inventory_item"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"), nullable=False)
    target_character_id = db.Column(db.Integer, db.ForeignKey("character.id"), index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    tags_json = db.Column(db.Text)
    source_prompt = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False, default="available", index=True)
    used_session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), index=True)
    used_character_id = db.Column(db.Integer, db.ForeignKey("character.id"), index=True)
    used_at = db.Column(db.DateTime)
