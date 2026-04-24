import os

import click
from flask import Flask, jsonify, redirect, send_from_directory, session as flask_session, url_for
from sqlalchemy import text

from .api import ApiError, error_response
from .config import Config
from .extensions import db, migrate, session
from .models import User
from .blueprints.ui import ui_bp
from .blueprints.auth import auth_bp
from .blueprints.chat import chat_bp
from .blueprints.projects import projects_bp
from .blueprints.worlds import worlds_bp
from .blueprints.characters import characters_bp
from .blueprints.scenes import scenes_bp
from .blueprints.assets import assets_bp
from .blueprints.jobs import jobs_bp
from .blueprints.glossary import glossary_bp
from .blueprints.story_outline import story_outline_bp
from .blueprints.chapters import chapters_bp
from .blueprints.scene_versions import scene_versions_bp
from .blueprints.scene_images import scene_images_bp
from .blueprints.ending_conditions import ending_conditions_bp
from .blueprints.exports import exports_bp
from .blueprints.settings import settings_bp


def _ensure_runtime_directories(app: Flask):
    instance_path = app.instance_path
    storage_root = app.config.get("STORAGE_ROOT")
    os.makedirs(instance_path, exist_ok=True)
    if storage_root:
        os.makedirs(storage_root, exist_ok=True)


def _register_cli_commands(app: Flask):
    @app.cli.command("create-user")
    @click.option("--email", prompt=True, help="Login email address.")
    @click.option("--display-name", prompt=True, help="Display name.")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="Login password.")
    @click.option("--status", default="active", show_default=True, help="User status.")
    def create_user_command(email: str, display_name: str, password: str, status: str):
        normalized_email = str(email).strip().lower()
        if not normalized_email:
            raise click.ClickException("email is required")

        user = User.query.filter_by(email=normalized_email).first()
        if user is None:
            user = User(email=normalized_email, display_name=display_name, status=status)
            db.session.add(user)
        else:
            user.display_name = display_name
            user.status = status

        user.set_password(password)
        db.session.commit()
        click.echo(f"user ready: {user.email} (id={user.id})")


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    _ensure_runtime_directories(app)

    db.init_app(app)
    app.config["SESSION_SQLALCHEMY"] = db
    session.init_app(app)
    migrate.init_app(app, db)
    _register_cli_commands(app)

    app.register_blueprint(ui_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(chat_bp, url_prefix="/api/v1")
    app.register_blueprint(projects_bp, url_prefix="/api/v1/projects")
    app.register_blueprint(worlds_bp, url_prefix="/api/v1")
    app.register_blueprint(characters_bp, url_prefix="/api/v1")
    app.register_blueprint(scenes_bp, url_prefix="/api/v1")
    app.register_blueprint(assets_bp, url_prefix="/api/v1")
    app.register_blueprint(jobs_bp, url_prefix="/api/v1")
    app.register_blueprint(glossary_bp, url_prefix="/api/v1")
    app.register_blueprint(story_outline_bp, url_prefix="/api/v1")
    app.register_blueprint(chapters_bp, url_prefix="/api/v1")
    app.register_blueprint(scene_versions_bp, url_prefix="/api/v1")
    app.register_blueprint(scene_images_bp, url_prefix="/api/v1")
    app.register_blueprint(ending_conditions_bp, url_prefix="/api/v1")
    app.register_blueprint(exports_bp, url_prefix="/api/v1")
    app.register_blueprint(settings_bp, url_prefix="/api/v1")

    @app.route("/", methods=["GET"])
    def index():
        if flask_session.get("user_id"):
            return redirect(url_for("ui.dashboard_page"))
        return redirect(url_for("ui.login_page"))

    @app.route("/media/<path:relative_path>", methods=["GET"])
    def media_file(relative_path: str):
        return send_from_directory(app.config["STORAGE_ROOT"], relative_path)

    @app.route("/health", methods=["GET"])
    def health_check():
        database_status = {"ok": True}
        try:
            db.session.execute(text("SELECT 1"))
        except Exception as exc:
            database_status = {"ok": False, "error": str(exc)}

        return jsonify(
            {
                "status": "ok" if database_status["ok"] else "degraded",
                "database": database_status,
                "config": {
                    "database_url": app.config.get("SQLALCHEMY_DATABASE_URI"),
                    "storage_root": app.config.get("STORAGE_ROOT"),
                },
            }
        )

    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return error_response(exc.message, status=exc.status_code, code=exc.code, meta=exc.meta)

    @app.errorhandler(ValueError)
    def handle_value_error(exc: ValueError):
        return error_response(str(exc), status=400, code="bad_request")

    @app.errorhandler(PermissionError)
    def handle_permission_error(exc: PermissionError):
        message = str(exc) or "unauthorized"
        return error_response(message, status=401, code="unauthorized")

    @app.errorhandler(LookupError)
    def handle_lookup_error(exc: LookupError):
        message = str(exc) or "not_found"
        return error_response(message, status=404, code="not_found")

    return app
