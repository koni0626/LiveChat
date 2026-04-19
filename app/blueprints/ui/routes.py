from __future__ import annotations

from flask import Blueprint, render_template, request, session, url_for


ui_bp = Blueprint("ui", __name__)


def _project_nav(project_id: int | None):
    if project_id is None:
        return []
    return [
        {"label": "作品トップ", "icon": "bi-grid-1x2", "href": url_for("ui.project_home_page", project_id=project_id)},
        {"label": "世界観", "icon": "bi-globe2", "href": url_for("ui.world_page", project_id=project_id)},
        {"label": "キャラクター", "icon": "bi-people", "href": url_for("ui.character_list_page", project_id=project_id)},
        {"label": "ストーリー骨子", "icon": "bi-diagram-3", "href": url_for("ui.story_outline_page", project_id=project_id)},
        {"label": "章一覧", "icon": "bi-list-ol", "href": url_for("ui.chapter_manage_page", project_id=project_id)},
        {"label": "シーン", "icon": "bi-film", "href": url_for("ui.scene_editor_page", project_id=project_id)},
        {"label": "エクスポート", "icon": "bi-box-arrow-up-right", "href": url_for("ui.export_page", project_id=project_id)},
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
            {"label": "作品一覧", "icon": "bi-collection", "href": url_for("ui.project_list_page")},
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
    return _render("ui/projects.html", title="作品一覧", screen_id="project-list")


@ui_bp.route("/projects/new", methods=["GET"])
def project_create_page():
    return _render("ui/project_new.html", title="作品新規作成", screen_id="project-create")


@ui_bp.route("/projects/<int:project_id>/home", methods=["GET"])
def project_home_page(project_id: int):
    return _render("ui/project_home.html", title="作品編集トップ", screen_id="project-home", project_id=project_id)


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


@ui_bp.route("/projects/<int:project_id>/story-outline", methods=["GET"])
def story_outline_page(project_id: int):
    return _render("ui/story_outline.html", title="ストーリー骨子設定", screen_id="story-outline", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/chapters/manage", methods=["GET"])
def chapter_manage_page(project_id: int):
    return _render("ui/chapter_manage.html", title="章一覧・編集", screen_id="chapter-manage", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/scenes", methods=["GET"])
def scene_editor_page(project_id: int):
    selected_scene_id = request.args.get("scene_id", type=int)
    return _render(
        "ui/scene_editor.html",
        title="シーン一覧・編集",
        screen_id="scene-editor",
        project_id=project_id,
        selected_scene_id=selected_scene_id,
    )


@ui_bp.route("/scenes/<int:scene_id>/candidates", methods=["GET"])
def scene_candidates_page(scene_id: int):
    project_id = request.args.get("project_id", type=int)
    return _render(
        "ui/scene_candidates.html",
        title="シーン生成結果確認",
        screen_id="scene-candidates",
        project_id=project_id,
        scene_id=scene_id,
    )


@ui_bp.route("/scenes/<int:scene_id>/images/review", methods=["GET"])
def image_review_page(scene_id: int):
    project_id = request.args.get("project_id", type=int)
    return _render(
        "ui/image_review.html",
        title="画像生成確認",
        screen_id="image-review",
        project_id=project_id,
        scene_id=scene_id,
    )


@ui_bp.route("/scenes/<int:scene_id>/preview", methods=["GET"])
def preview_page(scene_id: int):
    project_id = request.args.get("project_id", type=int)
    return _render("ui/preview.html", title="プレビュー", screen_id="preview", project_id=project_id, scene_id=scene_id)


@ui_bp.route("/projects/<int:project_id>/exports", methods=["GET"])
def export_page(project_id: int):
    return _render("ui/export.html", title="エクスポート", screen_id="export", project_id=project_id)


@ui_bp.route("/settings", methods=["GET"])
def settings_page():
    return _render("ui/settings.html", title="設定", screen_id="settings")
