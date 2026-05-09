from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class CharacterLineMessage(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "character_line_message"

    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey("character_line_room.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    sender_type = db.Column(db.String(30), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    body = db.Column(db.Text, nullable=False)
    turn_index = db.Column(db.Integer, nullable=False, default=0)
    generation_batch = db.Column(db.String(80), index=True)
    metadata_json = db.Column(db.Text)
