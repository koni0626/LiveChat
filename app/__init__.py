import os
from pathlib import Path

import click
from flask import Flask, jsonify, redirect, send_from_directory, session as flask_session, url_for, request
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
from .blueprints.cinema_novels import cinema_novels_bp
from .blueprints.character_lines import character_lines_bp


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
            user = User(email=normalized_email, display_name=display_name, player_name=display_name, status=status, role=role)
            db.session.add(user)
        else:
            user.display_name = display_name
            if not str(getattr(user, "player_name", "") or "").strip():
                user.player_name = display_name
            user.status = status
            user.role = role

        user.set_password(password)
        db.session.commit()
        click.echo(f"user ready: {user.email} (id={user.id}, role={user.role})")

    @app.cli.command("generate-character-actions")
    @click.option("--project-id", required=True, type=int, help="Project id to generate autonomous character actions for.")
    @click.option("--count", default=3, show_default=True, type=int, help="Number of action logs to generate.")
    @click.option("--target", default="feed", show_default=True, type=click.Choice(["feed", "news", "both"]), help="Where to publish generated actions.")
    @click.option("--status", default="published", show_default=True, type=click.Choice(["published", "draft"]), help="Feed post status.")
    @click.option("--user-id", type=int, help="Creator user id. Defaults to the project owner.")
    @click.option("--dry-run", is_flag=True, help="Preview generated actions without saving.")
    @click.option("--no-ai", is_flag=True, help="Use deterministic fallback generation without calling the text AI.")
    @click.option("--with-images", is_flag=True, help="Generate romantic-comedy style Feed images for created Feed posts.")
    @click.option("--image-size", default="1536x1024", show_default=True, help="Image size for generated Feed images.")
    @click.option("--image-quality", default=None, help="Image quality for generated Feed images. Defaults to app setting.")
    def generate_character_actions_command(
        project_id: int,
        count: int,
        target: str,
        status: str,
        user_id: int | None,
        dry_run: bool,
        no_ai: bool,
        with_images: bool,
        image_size: str,
        image_quality: str | None,
    ):
        from .services.autonomous_character_action_service import AutonomousCharacterActionService
        from .utils import json_util

        service = AutonomousCharacterActionService()
        if dry_run:
            result = service.preview_actions(project_id=project_id, count=count, use_ai=not no_ai)
        else:
            result = service.generate_actions(
                project_id=project_id,
                created_by_user_id=user_id,
                count=count,
                target=target,
                status=status,
                use_ai=not no_ai,
                with_images=with_images,
                image_size=image_size,
                image_quality=image_quality,
            )
        click.echo(json_util.dumps(result, indent=2))

    @app.cli.command("generate-character-line-thread")
    @click.option("--project-id", required=True, type=int, help="Project id to generate a character LINE thread for.")
    @click.option("--theme", required=True, help="Initial topic thrown in by the player.")
    @click.option("--player-comment", default=None, help="Optional follow-up comment from the player.")
    @click.option("--turns", default=20, show_default=True, type=int, help="Maximum number of LINE messages to generate.")
    @click.option("--participants", default=8, show_default=True, type=int, help="Number of participating characters.")
    @click.option("--exact-turns", is_flag=True, help="Generate exactly --turns messages instead of ending naturally.")
    @click.option("--no-ai", is_flag=True, help="Use deterministic fallback generation without calling the text AI.")
    @click.option("--json", "as_json", is_flag=True, help="Print raw JSON instead of LINE-style text.")
    def generate_character_line_thread_command(
        project_id: int,
        theme: str,
        player_comment: str | None,
        turns: int,
        participants: int,
        exact_turns: bool,
        no_ai: bool,
        as_json: bool,
    ):
        from .services.character_line_thread_service import CharacterLineThreadService
        from .utils import json_util

        service = CharacterLineThreadService()
        result = service.generate_thread(
            project_id=project_id,
            theme=theme,
            turns=turns,
            participant_count=participants,
            player_comment=player_comment,
            exact_turns=exact_turns,
            use_ai=not no_ai,
        )
        click.echo(json_util.dumps(result, indent=2) if as_json else service.format_thread_text(result))


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
    app.register_blueprint(cinema_novels_bp, url_prefix="/api/v1")
    app.register_blueprint(character_lines_bp, url_prefix="/api/v1")

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
        response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if app.config.get("SECURITY_CSP_ENABLED", True):
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                "font-src 'self' https://cdn.jsdelivr.net https://fonts.gstatic.com data:; "
                "img-src 'self' data: blob:; "
                "connect-src 'self'; "
                "frame-ancestors 'self'; "
                "base-uri 'self'; "
                "form-action 'self'",
            )
        if app.config.get("SECURITY_HSTS_ENABLED") and request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
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
        normalized_relative = relative_path.replace("\\", "/")
        parts = [part for part in normalized_relative.split("/") if part]
        if not parts or any(part in {".", ".."} for part in parts) or Path(normalized_relative).is_absolute():
            return error_response("not_found", status=404, code="not_found")
        storage_root = Path(app.config["STORAGE_ROOT"]).resolve()
        requested_path = (storage_root / normalized_relative).resolve()
        try:
            requested_path.relative_to(storage_root)
        except ValueError:
            return error_response("not_found", status=404, code="not_found")
        if not requested_path.is_file():
            return error_response("not_found", status=404, code="not_found")
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
        response = send_from_directory(str(storage_root), normalized_relative)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Cache-Control", "private, max-age=3600")
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
