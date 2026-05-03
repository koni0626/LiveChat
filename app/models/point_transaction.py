from ..extensions import db
from .base import CreatedAtMixin


class PointTransaction(db.Model, CreatedAtMixin):
    __tablename__ = "point_transaction"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), index=True)
    action_type = db.Column(db.String(100), nullable=False, index=True)
    points_delta = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), default="success", nullable=False, index=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), index=True)
    message_id = db.Column(db.Integer, db.ForeignKey("chat_message.id"), index=True)
    image_id = db.Column(db.Integer, db.ForeignKey("session_image.id"), index=True)
    detail_json = db.Column(db.Text)
