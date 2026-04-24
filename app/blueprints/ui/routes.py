from __future__ import annotations

from flask import Blueprint, render_template, session, url_for


ui_bp = Blueprint("ui", __name__)


def _project_nav(project_id: int | None):
    if project_id is None:
        return []
    return [
        {"label": "ホーム", "icon": "bi-grid-1x2", "href": url_for("ui.project_home_page", project_id=project_id)},
        {"label": "世界観", "icon": "bi-globe2", "href": url_for("ui.world_page", project_id=project_id)},
        {"label": "キャラクター", "icon": "bi-people", "href": url_for("ui.character_list_page", project_id=project_id)},
        {"label": "ライブチャット", "icon": "bi-chat-dots", "href": url_for("ui.live_chat_sessions_page", project_id=project_id)},
    ]


def _render(template_name: str, *, title: str, screen_id: str, project_id: int | None = None, **context):
    user_id = session.get("user_id")
    return render_template(
        template_name,
        page_title=title,
        screen_id=screen_id,
        project_id=project_id,
        current_user_id=user_id,
        project_nav_links=_project_nav(project_id),
        global_nav_links=[
            {"label": "ダッシュボード", "icon": "bi-house-door", "href": url_for("ui.dashboard_page")},
            {"label": "プロジェクト", "icon": "bi-collection", "href": url_for("ui.project_list_page")},
            {"label": "設定", "icon": "bi-sliders", "href": url_for("ui.settings_page")},
        ],
        **context,
    )


@ui_bp.route("/login", methods=["GET"])
def login_page():
    return _render("ui/login.html", title="ログイン", screen_id="login")


@ui_bp.route("/register", methods=["GET"])
def register_page():
    return _render("ui/register.html", title="ユーザー登録", screen_id="register")


@ui_bp.route("/dashboard", methods=["GET"])
def dashboard_page():
    return _render("ui/dashboard.html", title="ダッシュボード", screen_id="dashboard")


@ui_bp.route("/projects", methods=["GET"])
def project_list_page():
    return _render("ui/projects.html", title="プロジェクト一覧", screen_id="project-list")


@ui_bp.route("/projects/new", methods=["GET"])
def project_create_page():
    return _render("ui/project_new.html", title="新規プロジェクト", screen_id="project-create")


@ui_bp.route("/projects/<int:project_id>/home", methods=["GET"])
def project_home_page(project_id: int):
    return _render("ui/project_home.html", title="プロジェクトホーム", screen_id="project-home", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/characters", methods=["GET"])
def character_list_page(project_id: int):
    return _render("ui/character_list.html", title="キャラクター一覧", screen_id="character-list", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/characters/new", methods=["GET"])
def character_create_page(project_id: int):
    return _render(
        "ui/character_edit.html",
        title="キャラクター作成",
        screen_id="character-create",
        project_id=project_id,
        character_id=None,
    )


@ui_bp.route("/projects/<int:project_id>/characters/<int:character_id>/edit", methods=["GET"])
def character_edit_page(project_id: int, character_id: int):
    return _render(
        "ui/character_edit.html",
        title="キャラクター編集",
        screen_id="character-edit",
        project_id=project_id,
        character_id=character_id,
    )


@ui_bp.route("/projects/<int:project_id>/world", methods=["GET"])
def world_page(project_id: int):
    return _render("ui/world_edit.html", title="世界観設定", screen_id="world-edit", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/live-chat", methods=["GET"])
def live_chat_sessions_page(project_id: int):
    return _render("ui/live_chat_sessions.html", title="ライブチャット", screen_id="live-chat-sessions", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/live-chat/<int:session_id>", methods=["GET"])
def live_chat_page(project_id: int, session_id: int):
    return _render(
        "ui/live_chat.html",
        title="ライブチャット",
        screen_id="live-chat",
        project_id=project_id,
        session_id=session_id,
    )


@ui_bp.route("/settings", methods=["GET"])
def settings_page():
    return _render("ui/settings.html", title="設定", screen_id="settings")
