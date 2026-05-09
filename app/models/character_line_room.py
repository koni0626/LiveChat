from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class CharacterLineRoom(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "character_line_room"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    participant_ids_json = db.Column(db.Text)
    is_default = db.Column(db.Boolean, nullable=False, default=False, index=True)
    last_theme = db.Column(db.Text)
    last_message_at = db.Column(db.DateTime)
