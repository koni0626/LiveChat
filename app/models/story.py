from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class Story(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "story"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"), nullable=False, index=True)
    character_id = db.Column(db.Integer, db.ForeignKey("character.id"), nullable=False, index=True)
    default_outfit_id = db.Column(db.Integer, db.ForeignKey("character_outfit.id"), index=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(50), nullable=False, default="draft", index=True)
    story_mode = db.Column(db.String(100), nullable=False, default="free_chat", index=True)
    config_markdown = db.Column(db.Text)
    config_json = db.Column(db.Text)
    initial_state_json = db.Column(db.Text)
    style_reference_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    main_character_reference_asset_id = db.Column(db.Integer, db.ForeignKey("asset.id"))
    sort_order = db.Column(db.Integer, nullable=False, default=0)
