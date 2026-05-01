from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .base import TimestampMixin, SoftDeleteMixin


class User(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    display_name = db.Column(db.String(255), nullable=False)
    player_name = db.Column(db.String(100))
    password_hash = db.Column(db.String(255))
    auth_provider = db.Column(db.String(50), default="local", nullable=False)
    role = db.Column(db.String(50), default="user", nullable=False)
    status = db.Column(db.String(50), default="active", nullable=False)

    def set_password(self, password: str):
        if password is None or str(password) == "":
            raise ValueError("password is required")
        if len(str(password)) < 8:
            raise ValueError("password must be at least 8 characters")
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password: str) -> bool:
        if not self.password_hash or password is None:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_active_user(self) -> bool:
        return self.status == "active" and self.deleted_at is None
