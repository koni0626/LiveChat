from __future__ import annotations

from typing import Any

from ..extensions import db
from ..models import User


class UserAdminService:
    VALID_ROLES = {"superuser", "project_user", "user"}
    VALID_STATUSES = {"active", "suspended", "deleted"}

    def list_users(self) -> list[dict[str, Any]]:
        return [self._serialize(user) for user in User.query.order_by(User.id.desc()).all()]

    def create_user(self, payload: dict | None) -> dict[str, Any]:
        payload = dict(payload or {})
        email = self._normalize_email(payload.get("email"))
        display_name = self._normalize_required(payload.get("display_name"), "display_name")
        password = self._normalize_required(payload.get("password"), "password")
        role = self._normalize_role(payload.get("role") or "project_user")
        status = self._normalize_status(payload.get("status") or "active")
        if User.query.filter_by(email=email).first():
            raise ValueError("email already exists")
        user = User(email=email, display_name=display_name, role=role, status=status, auth_provider="local")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return self._serialize(user)

    def update_user(self, user_id: int, payload: dict | None) -> dict[str, Any] | None:
        payload = dict(payload or {})
        user = User.query.get(user_id)
        if not user:
            return None
        if "display_name" in payload:
            user.display_name = self._normalize_required(payload.get("display_name"), "display_name")
        if "role" in payload:
            user.role = self._normalize_role(payload.get("role"))
        if "status" in payload:
            user.status = self._normalize_status(payload.get("status"))
        if payload.get("password"):
            user.set_password(str(payload["password"]))
        db.session.commit()
        return self._serialize(user)

    def _serialize(self, user: User) -> dict[str, Any]:
        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "role": getattr(user, "role", "user") or "user",
            "status": user.status,
            "auth_provider": user.auth_provider,
            "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
            "updated_at": user.updated_at.isoformat() if getattr(user, "updated_at", None) else None,
        }

    def _normalize_email(self, value) -> str:
        email = str(value or "").strip().lower()
        if not email:
            raise ValueError("email is required")
        return email

    def _normalize_required(self, value, field_name: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{field_name} is required")
        return text

    def _normalize_role(self, value) -> str:
        role = str(value or "").strip()
        if role not in self.VALID_ROLES:
            raise ValueError("role is invalid")
        return role

    def _normalize_status(self, value) -> str:
        status = str(value or "").strip()
        if status not in self.VALID_STATUSES:
            raise ValueError("status is invalid")
        return status
