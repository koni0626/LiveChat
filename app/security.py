from __future__ import annotations

import hmac
import secrets
from time import monotonic

from flask import current_app, request, session

from .api import ForbiddenError, ValidationError


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_login_attempts: dict[str, list[float]] = {}


def ensure_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf_request() -> None:
    if not current_app.config.get("CSRF_ENABLED", True):
        return
    if current_app.testing:
        return
    if request.method not in UNSAFE_METHODS:
        return
    if not request.path.startswith("/api/"):
        return
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRFToken") or request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not hmac.compare_digest(str(expected), str(supplied)):
        raise ForbiddenError("csrf token is invalid", code="csrf_invalid")


def validate_secret_key(app) -> None:
    secret_key = str(app.config.get("SECRET_KEY") or "")
    if secret_key and secret_key != "dev-secret":
        return
    if app.config.get("REQUIRE_STRONG_SECRET_KEY"):
        raise RuntimeError("SECRET_KEY must be set to a strong random value in production")
    if not app.debug and not app.testing:
        app.logger.warning("SECRET_KEY is using an unsafe development default")


def login_rate_limit_key(email: str | None) -> str:
    remote_addr = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",", 1)[0].strip()
    normalized_email = str(email or "").strip().lower()
    return f"{remote_addr}:{normalized_email}"


def check_login_rate_limit(key: str) -> None:
    now = monotonic()
    window = int(current_app.config.get("AUTH_RATE_LIMIT_WINDOW_SECONDS", 900))
    max_attempts = int(current_app.config.get("AUTH_RATE_LIMIT_ATTEMPTS", 10))
    attempts = [timestamp for timestamp in _login_attempts.get(key, []) if now - timestamp < window]
    _login_attempts[key] = attempts
    if len(attempts) >= max_attempts:
        raise ValidationError("too many login attempts", code="rate_limited")


def record_login_failure(key: str) -> None:
    _login_attempts.setdefault(key, []).append(monotonic())


def clear_login_failures(key: str) -> None:
    _login_attempts.pop(key, None)
