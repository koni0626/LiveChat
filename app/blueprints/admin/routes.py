from flask import Blueprint, request

from ...api import ForbiddenError, NotFoundError, json_response
from ...services.authorization_service import AuthorizationService
from ...services.user_admin_service import UserAdminService
from ..access import current_user_or_401


admin_bp = Blueprint("admin", __name__)
authorization_service = AuthorizationService()
user_admin_service = UserAdminService()


def _require_superuser():
    user = current_user_or_401()
    if not authorization_service.is_superuser(user):
        raise ForbiddenError()
    return user


@admin_bp.route("/admin/users", methods=["GET"])
def list_users():
    _require_superuser()
    return json_response(user_admin_service.list_users())


@admin_bp.route("/admin/users", methods=["POST"])
def create_user():
    _require_superuser()
    payload = request.get_json(silent=True) or {}
    user = user_admin_service.create_user(payload)
    return json_response(user, status=201)


@admin_bp.route("/admin/users/<int:user_id>", methods=["PATCH"])
def update_user(user_id: int):
    _require_superuser()
    user = user_admin_service.update_user(user_id, request.get_json(silent=True) or {})
    if not user:
        raise NotFoundError()
    return json_response(user)
