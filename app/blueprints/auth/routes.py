from flask import Blueprint, request, session
from ...api import json_response
from app.services.auth_service import AuthService
from ...security import check_login_rate_limit, clear_login_failures, login_rate_limit_key, record_login_failure

auth_bp = Blueprint("auth", __name__)
auth_service = AuthService()
def _set_session_user(user_id: int | None):
    session.clear()
    if user_id:
        session["user_id"] = user_id
        session.permanent = True


def _get_session_user_id() -> int | None:
    return session.get("user_id")


@auth_bp.route("/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email")
    password = payload.get("password")
    rate_key = login_rate_limit_key(email)

    try:
        check_login_rate_limit(rate_key)
        result = auth_service.login(email=email, password=password)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    except PermissionError:
        record_login_failure(rate_key)
        return json_response({"message": "invalid credentials"}, status=401)

    clear_login_failures(rate_key)
    _set_session_user(result["user"]["id"])
    return json_response(result)


@auth_bp.route("/register", methods=["POST"])
def register():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email")
    display_name = payload.get("display_name")
    password = payload.get("password")

    try:
        result = auth_service.register(email=email, display_name=display_name, password=password)
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)

    _set_session_user(result["user"]["id"])
    return json_response(result, status=201)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    user_id = _get_session_user_id()
    _set_session_user(None)
    result = auth_service.logout(user_id=user_id)
    return json_response(result)


@auth_bp.route("/me", methods=["GET"])
def me():
    user_id = _get_session_user_id()
    user = auth_service.get_current_user(user_id)
    if not user:
        _set_session_user(None)
        return json_response({"user": None}, status=401)

    return json_response({"user": user})
