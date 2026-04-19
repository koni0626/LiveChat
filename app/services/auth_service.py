import secrets
from typing import Any, Optional

from ..extensions import db
from ..models import User
from .usage_log_service import UsageLogService


class AuthService:
    def __init__(self, usage_log_service: Optional[UsageLogService] = None) -> None:
        self._usage_log_service = usage_log_service or UsageLogService()

    def _normalize_email(self, email: Optional[str]) -> str:
        if email is None:
            raise ValueError("email is required")
        value = str(email).strip().lower()
        if not value:
            raise ValueError("email is required")
        return value

    def _validate_password(self, password: Optional[str]) -> str:
        if password is None or password == "":
            raise ValueError("password is required")
        return password

    def _validate_display_name(self, display_name: Optional[str]) -> str:
        if display_name is None:
            raise ValueError("display_name is required")
        value = str(display_name).strip()
        if not value:
            raise ValueError("display_name is required")
        return value

    def _serialize_user(self, user: User) -> dict[str, Any]:
        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "status": user.status,
            "auth_provider": user.auth_provider,
        }

    def _generate_token(self, user: User) -> str:
        return secrets.token_urlsafe(32)

    def _get_active_user_by_email(self, email: str) -> Optional[User]:
        user = User.query.filter_by(email=email).first()
        if not user or not user.is_active_user:
            return None
        return user

    def _get_user_by_email(self, email: str) -> Optional[User]:
        return User.query.filter_by(email=email).first()

    def _log_auth_event(self, user_id: Optional[int], action_type: str):
        if not user_id:
            return
        try:
            self._usage_log_service.create_log(
                {
                    "user_id": user_id,
                    "action_type": action_type,
                    "quantity": 1,
                    "unit": "event",
                }
            )
        except Exception:
            return

    def login(self, email: Optional[str], password: Optional[str]) -> dict[str, Any]:
        normalized_email = self._normalize_email(email)
        password = self._validate_password(password)

        user = self._get_active_user_by_email(normalized_email)
        if not user or not user.password_hash:
            raise PermissionError("invalid credentials")

        if not user.verify_password(password):
            raise PermissionError("invalid credentials")

        self._log_auth_event(user.id, "auth_login")
        return {
            "token": self._generate_token(user),
            "auth_mode": "session",
            "user": self._serialize_user(user),
        }

    def register(self, email: Optional[str], display_name: Optional[str], password: Optional[str]) -> dict[str, Any]:
        normalized_email = self._normalize_email(email)
        validated_display_name = self._validate_display_name(display_name)
        validated_password = self._validate_password(password)

        existing_user = self._get_user_by_email(normalized_email)
        if existing_user is not None:
            raise ValueError("email already exists")

        user = User(
            email=normalized_email,
            display_name=validated_display_name,
            auth_provider="local",
            status="active",
        )
        user.set_password(validated_password)

        db.session.add(user)
        db.session.commit()

        self._log_auth_event(user.id, "auth_register")
        return {
            "token": self._generate_token(user),
            "auth_mode": "session",
            "user": self._serialize_user(user),
        }

    def logout(self, user_id: Optional[int] = None) -> dict[str, str]:
        self._log_auth_event(user_id, "auth_logout")
        return {"message": "logged out", "auth_mode": "session"}

    def get_current_user(self, user_id: Optional[int]):
        if user_id is None:
            return None
        user = User.query.get(user_id)
        if not user or not user.is_active_user:
            return None
        return self._serialize_user(user)
