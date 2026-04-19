from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class Asset(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "asset"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("project.id"))
    asset_type = db.Column(db.String(100), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    mime_type = db.Column(db.String(100))
    file_size = db.Column(db.Integer)
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    checksum = db.Column(db.String(255))
    metadata_json = db.Column(db.Text)
