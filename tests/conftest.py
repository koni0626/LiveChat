from pathlib import Path

import pytest

from app import create_app
from app.extensions import db


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + str((Path(__file__).parent / "test_app.db").resolve())
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    SESSION_TYPE = "filesystem"
    SESSION_PERMANENT = False


@pytest.fixture()
def app():
    db_path = Path(__file__).parent / "test_app.db"
    if db_path.exists():
        db_path.unlink()

    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

    if db_path.exists():
        db_path.unlink()


@pytest.fixture()
def client(app):
    return app.test_client()
