from ..extensions import db
from .base import TimestampMixin


class UserSetting(db.Model, TimestampMixin):
    __tablename__ = "user_setting"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True, index=True)
    text_ai_model = db.Column(db.String(100), nullable=False, default="gpt-5.4-mini")
    image_ai_provider = db.Column(db.String(20), nullable=False, default="openai")
    image_ai_model = db.Column(db.String(100), nullable=False, default="gpt-image-2")
    default_quality = db.Column(db.String(20), nullable=False, default="medium")
    default_size = db.Column(db.String(20), nullable=False, default="1024x1024")
    prefer_portrait_on_mobile = db.Column(db.Boolean, nullable=False, default=False)
    autosave_interval = db.Column(db.String(20), nullable=False, default="off")
    cinema_novel_text_model = db.Column(db.String(100), nullable=False, default="gpt-5.5")
    cinema_novel_image_ai_provider = db.Column(db.String(20), nullable=False, default="openai")
    cinema_novel_image_ai_model = db.Column(db.String(100), nullable=False, default="gpt-image-2")
    cinema_novel_default_quality = db.Column(db.String(20), nullable=False, default="high")
    cinema_novel_default_size = db.Column(db.String(20), nullable=False, default="1536x1024")
    cinema_novel_chapter_target_chars = db.Column(db.Integer, nullable=False, default=8000)
