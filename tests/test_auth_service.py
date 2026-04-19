import pytest
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User
from app.services.auth_service import AuthService


def test_auth_service_login_success(app):
    with app.app_context():
        user = User(
            email="user@example.com",
            display_name="tester",
            password_hash=generate_password_hash("secret123"),
            status="active",
        )
        db.session.add(user)
        db.session.commit()

        service = AuthService()
        result = service.login("user@example.com", "secret123")

        assert result["user"]["email"] == "user@example.com"
        assert result["user"]["display_name"] == "tester"
        assert isinstance(result["token"], str)
        assert result["token"]


def test_auth_service_login_invalid_password(app):
    with app.app_context():
        user = User(
            email="user@example.com",
            display_name="tester",
            password_hash=generate_password_hash("secret123"),
            status="active",
        )
        db.session.add(user)
        db.session.commit()

        service = AuthService()

        with pytest.raises(PermissionError):
            service.login("user@example.com", "wrong-password")


def test_auth_service_get_current_user_ignores_inactive_user(app):
    with app.app_context():
        user = User(
            email="inactive@example.com",
            display_name="inactive",
            password_hash=generate_password_hash("secret123"),
            status="disabled",
        )
        db.session.add(user)
        db.session.commit()

        service = AuthService()

        assert service.get_current_user(user.id) is None
