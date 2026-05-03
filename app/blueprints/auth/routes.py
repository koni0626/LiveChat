from flask import Blueprint, request, session
from ...extensions import db
from ...models import User
from ...api import json_response
from app.services.auth_service import AuthService
from app.services.point_service import PointService
from ...security import (
    check_login_rate_limit,
    clear_login_failures,
    login_rate_limit_key,
    record_login_failure,
    test_point_purchase_enabled,
)

auth_bp = Blueprint("auth", __name__)
auth_service = AuthService()
point_service = PointService()
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


@auth_bp.route("/me/player-name", methods=["PATCH"])
def update_player_name():
    user_id = _get_session_user_id()
    if not user_id:
        return json_response({"message": "unauthorized"}, status=401)
    row = User.query.get(user_id)
    if not row or not row.is_active_user:
        _set_session_user(None)
        return json_response({"message": "unauthorized"}, status=401)
    payload = request.get_json(silent=True) or {}
    player_name = str(payload.get("player_name") or "").strip()
    if not player_name:
        return json_response({"message": "player_name is required"}, status=400)
    row.player_name = player_name[:100]
    db.session.add(row)
    db.session.commit()
    return json_response({"user": auth_service.get_current_user(row.id)})


@auth_bp.route("/points/test-purchase", methods=["POST"])
def test_purchase_points():
    if not test_point_purchase_enabled():
        return json_response({"message": "test point purchase is disabled"}, status=403)
    user_id = _get_session_user_id()
    if not user_id:
        return json_response({"message": "unauthorized"}, status=401)
    row = User.query.get(user_id)
    if not row or not row.is_active_user:
        _set_session_user(None)
        return json_response({"message": "unauthorized"}, status=401)
    payload = request.get_json(silent=True) or {}
    try:
        amount = int(payload.get("amount"))
    except (TypeError, ValueError):
        return json_response({"message": "amount must be an integer"}, status=400)
    try:
        transaction = point_service.test_purchase(
            row,
            amount=amount,
            detail={"note": str(payload.get("note") or "").strip()[:255] or None},
        )
    except ValueError as exc:
        return json_response({"message": str(exc)}, status=400)
    return json_response(
        {
            "points": {
                "delta": transaction.points_delta,
                "balance": transaction.balance_after,
                "action_type": transaction.action_type,
            },
            "user": auth_service.get_current_user(row.id),
        },
        status=201,
    )
