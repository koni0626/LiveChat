from __future__ import annotations

from flask import session

from ..api import ForbiddenError, NotFoundError, UnauthorizedError
from ..models import User
from ..services.authorization_service import AuthorizationService
from ..services.project_service import ProjectService


authorization_service = AuthorizationService()
project_service = ProjectService()


def current_user_or_401():
    user_id = session.get("user_id")
    if not user_id:
        raise UnauthorizedError()
    user = User.query.get(user_id)
    if not user or not user.is_active_user:
        raise UnauthorizedError()
    return user


def require_project_view(project_id: int):
    user = current_user_or_401()
    project = project_service.get_project(project_id)
    if not project or not authorization_service.can_view_project(user, project):
        raise NotFoundError()
    return project, user


def require_project_manage(project_id: int):
    user = current_user_or_401()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if not authorization_service.can_manage_project(user, project):
        raise ForbiddenError()
    return project, user
