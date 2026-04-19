from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User


def _create_user(email="user@example.com", password="secret123", display_name="tester", status="active"):
    user = User(
        email=email,
        display_name=display_name,
        password_hash=generate_password_hash(password),
        status=status,
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_auth_login_and_me_happy_path(app, client):
    with app.app_context():
        _create_user()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "secret123"},
    )

    assert login_response.status_code == 200
    login_payload = login_response.get_json()
    assert login_payload["data"]["user"]["email"] == "user@example.com"
    assert login_payload["data"]["token"]

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    me_payload = me_response.get_json()
    assert me_payload["data"]["user"]["email"] == "user@example.com"


def test_auth_logout_clears_session(app, client):
    with app.app_context():
        _create_user()

    client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "secret123"},
    )

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 200
    assert logout_response.get_json()["data"]["message"] == "logged out"

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 401
    assert me_response.get_json()["data"]["user"] is None
