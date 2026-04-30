import os

import click
from flask import Flask, jsonify, redirect, send_from_directory, session as flask_session, url_for
from sqlalchemy import text

from .api import ApiError, error_response
from .config import Config
from .extensions import db, migrate, session
from .models import User
from .security import ensure_csrf_token, validate_csrf_request, validate_secret_key
from .services.authorization_service import AuthorizationService
from .services.project_service import ProjectService
from .blueprints.ui import ui_bp
from .blueprints.auth import auth_bp
from .blueprints.chat import chat_bp
from .blueprints.projects import projects_bp
from .blueprints.worlds import worlds_bp
from .blueprints.characters import characters_bp
from .blueprints.assets import assets_bp
from .blueprints.admin import admin_bp
from .blueprints.settings import settings_bp
from .blueprints.letters import letters_bp
from .blueprints.feed import feed_bp
from .blueprints.stories import stories_bp
from .blueprints.studio import studio_bp
from .blueprints.world_maps import world_maps_bp
from .blueprints.outings import outings_bp
from .blueprints.world_news import world_news_bp
from .blueprints.closet import closet_bp


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
    @click.option(
        "--role",
        default="user",
        show_default=True,
        type=click.Choice(["superuser", "project_user", "user"]),
        help="User role.",
    )
    def create_user_command(email: str, display_name: str, password: str, status: str, role: str):
        normalized_email = str(email).strip().lower()
        if not normalized_email:
            raise click.ClickException("email is required")

        user = User.query.filter_by(email=normalized_email).first()
        if user is None:
            user = User(email=normalized_email, display_name=display_name, status=status, role=role)
            db.session.add(user)
        else:
            user.display_name = display_name
            user.status = status
            user.role = role

        user.set_password(password)
        db.session.commit()
        click.echo(f"user ready: {user.email} (id={user.id}, role={user.role})")


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    validate_secret_key(app)
    _ensure_runtime_directories(app)

    db.init_app(app)
    app.config["SESSION_SQLALCHEMY"] = db
    session.init_app(app)
    migrate.init_app(app, db)
    _register_cli_commands(app)
    authorization_service = AuthorizationService()
    project_service = ProjectService()

    app.register_blueprint(ui_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(chat_bp, url_prefix="/api/v1")
    app.register_blueprint(projects_bp, url_prefix="/api/v1/projects")
    app.register_blueprint(worlds_bp, url_prefix="/api/v1")
    app.register_blueprint(characters_bp, url_prefix="/api/v1")
    app.register_blueprint(assets_bp, url_prefix="/api/v1")
    app.register_blueprint(admin_bp, url_prefix="/api/v1")
    app.register_blueprint(settings_bp, url_prefix="/api/v1")
    app.register_blueprint(letters_bp, url_prefix="/api/v1")
    app.register_blueprint(feed_bp, url_prefix="/api/v1")
    app.register_blueprint(stories_bp, url_prefix="/api/v1")
    app.register_blueprint(studio_bp, url_prefix="/api/v1")
    app.register_blueprint(world_maps_bp, url_prefix="/api/v1")
    app.register_blueprint(outings_bp, url_prefix="/api/v1")
    app.register_blueprint(world_news_bp, url_prefix="/api/v1")
    app.register_blueprint(closet_bp, url_prefix="/api/v1")

    @app.before_request
    def enforce_csrf_protection():
        validate_csrf_request()

    @app.context_processor
    def inject_security_context():
        return {"csrf_token": ensure_csrf_token()}

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response

    @app.route("/", methods=["GET"])
    def index():
        user_id = flask_session.get("user_id")
        if user_id:
            current_user = User.query.get(user_id)
            if current_user and getattr(current_user, "role", "user") == "user":
                return redirect(url_for("ui.project_list_page"))
            return redirect(url_for("ui.dashboard_page"))
        return redirect(url_for("ui.login_page"))

    @app.route("/media/<path:relative_path>", methods=["GET"])
    def media_file(relative_path: str):
        parts = [part for part in relative_path.replace("\\", "/").split("/") if part]
        if parts[:1] == ["projects"] and len(parts) >= 2:
            try:
                project_id = int(parts[1])
            except (TypeError, ValueError):
                return error_response("not_found", status=404, code="not_found")
            user_id = flask_session.get("user_id")
            user = User.query.get(user_id) if user_id else None
            project = project_service.get_project(project_id)
            if not authorization_service.can_view_project(user, project):
                return error_response("not_found", status=404, code="not_found")
        else:
            user_id = flask_session.get("user_id")
            user = User.query.get(user_id) if user_id else None
            if not user or not user.is_active_user:
                return error_response("unauthorized", status=401, code="unauthorized")
        response = send_from_directory(app.config["STORAGE_ROOT"], relative_path)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        return response

    @app.route("/health", methods=["GET"])
    def health_check():
        database_status = {"ok": True}
        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            database_status = {"ok": False}

        return jsonify(
            {
                "status": "ok" if database_status["ok"] else "degraded",
                "database": database_status,
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
