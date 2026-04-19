from datetime import datetime

from ..extensions import db


class CreatedAtMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class TimestampMixin(CreatedAtMixin):
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime)
