from __future__ import annotations

from ..models import User


class AuthorizationService:
    ROLE_SUPERUSER = "superuser"
    ROLE_PROJECT_USER = "project_user"
    ROLE_USER = "user"

    def is_superuser(self, user: User | dict | None) -> bool:
        return self._role(user) == self.ROLE_SUPERUSER

    def is_project_user(self, user: User | dict | None) -> bool:
        return self._role(user) == self.ROLE_PROJECT_USER

    def can_create_project(self, user: User | dict | None) -> bool:
        return self._role(user) in {self.ROLE_SUPERUSER, self.ROLE_PROJECT_USER}

    def can_manage_project(self, user: User | dict | None, project) -> bool:
        if not user or not project:
            return False
        if self.is_superuser(user):
            return True
        return self.is_project_user(user) and getattr(project, "owner_user_id", None) == self._user_id(user)

    def can_view_project(self, user: User | dict | None, project) -> bool:
        if not user or not project:
            return False
        if self.can_manage_project(user, project):
            return True
        return (
            str(getattr(project, "status", "draft") or "draft") == "published"
            and bool(getattr(project, "chat_enabled", 1))
        )

    def can_create_chat_session(self, user: User | dict | None, project) -> bool:
        if not user or not project:
            return False
        if self.can_manage_project(user, project):
            return True
        return (
            str(getattr(project, "status", "draft") or "draft") == "published"
            and bool(getattr(project, "chat_enabled", 1))
        )

    def can_view_chat_session(self, user: User | dict | None, chat_session, project=None, *, include_body: bool = True) -> bool:
        if not user or not chat_session:
            return False
        if self.is_superuser(user):
            return True
        if getattr(chat_session, "owner_user_id", None) == self._user_id(user):
            return True
        if include_body:
            return False
        return bool(project) and self.can_manage_project(user, project)

    def can_manage_chat_session(self, user: User | dict | None, chat_session) -> bool:
        if not user or not chat_session:
            return False
        if self.is_superuser(user):
            return True
        return getattr(chat_session, "owner_user_id", None) == self._user_id(user)

    def _role(self, user: User | dict | None) -> str:
        if not user:
            return ""
        if isinstance(user, dict):
            return str(user.get("role") or self.ROLE_USER)
        return str(getattr(user, "role", None) or self.ROLE_USER)

    def _user_id(self, user: User | dict | None) -> int | None:
        if not user:
            return None
        if isinstance(user, dict):
            value = user.get("id")
        else:
            value = getattr(user, "id", None)
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
