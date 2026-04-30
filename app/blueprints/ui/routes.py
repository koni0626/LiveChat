from __future__ import annotations

from flask import Blueprint, redirect, render_template, session, url_for

from ...models import User
from ...services.authorization_service import AuthorizationService
from ...services.project_service import ProjectService


ui_bp = Blueprint("ui", __name__)
authorization_service = AuthorizationService()
project_service = ProjectService()


def _project_nav(project_id: int | None, current_user: User | None = None):
    if project_id is None:
        return []
    project = project_service.get_project(project_id)
    can_manage_project = authorization_service.can_manage_project(current_user, project)
    links = [
        {"label": "ホーム", "icon": "bi-grid-1x2", "href": url_for("ui.project_home_page", project_id=project_id)},
    ]
    if can_manage_project:
        links.append({"label": "世界観", "icon": "bi-globe2", "href": url_for("ui.world_page", project_id=project_id)})
        links.append({"label": "ワールドマップ", "icon": "bi-map", "href": url_for("ui.world_map_page", project_id=project_id)})
        links.append({"label": "おでかけ", "icon": "bi-signpost-split", "href": url_for("ui.outings_page", project_id=project_id)})
        links.append({"label": "ワールドニュース", "icon": "bi-newspaper", "href": url_for("ui.world_news_page", project_id=project_id)})
        links.append({"label": "キャラクター", "icon": "bi-people", "href": url_for("ui.character_list_page", project_id=project_id)})
        links.append({"label": "ルーム", "icon": "bi-chat-square-heart", "href": url_for("ui.live_chat_rooms_page", project_id=project_id)})
        links.append({"label": "ストーリー", "icon": "bi-journal-richtext", "href": url_for("ui.story_list_page", project_id=project_id)})
    else:
        links.append({"label": "ワールドマップ", "icon": "bi-map", "href": url_for("ui.world_map_page", project_id=project_id)})
        links.append({"label": "おでかけ", "icon": "bi-signpost-split", "href": url_for("ui.outings_page", project_id=project_id)})
        links.append({"label": "ワールドニュース", "icon": "bi-newspaper", "href": url_for("ui.world_news_page", project_id=project_id)})
    links.append({"label": "チャットルーム", "icon": "bi-chat-dots", "href": url_for("ui.live_chat_sessions_page", project_id=project_id)})
    links.append({"label": "セッション", "icon": "bi-dice-5", "href": url_for("ui.story_session_list_page", project_id=project_id)})
    links.append({"label": "スタジオ", "icon": "bi-palette", "href": url_for("ui.studio_page", project_id=project_id)})
    links.append({"label": "クローゼット", "icon": "bi-person-bounding-box", "href": url_for("ui.closet_page", project_id=project_id)})
    return links


def _render(template_name: str, *, title: str, screen_id: str, project_id: int | None = None, **context):
    user_id = session.get("user_id")
    current_user = User.query.get(user_id) if user_id else None
    if screen_id not in {"login", "register"} and not current_user:
        return redirect(url_for("ui.login_page"))
    current_project = project_service.get_project(project_id) if project_id else None
    can_manage_project = authorization_service.can_manage_project(current_user, current_project)
    if project_id and not authorization_service.can_view_project(current_user, current_project):
        return redirect(url_for("ui.project_list_page"))
    if screen_id in {
        "character-list",
        "character-create",
        "character-edit",
        "world-edit",
        "story-edit",
        "live-chat-rooms",
        "live-chat-room-edit",
    } and not can_manage_project:
        return redirect(url_for("ui.project_home_page", project_id=project_id))
    if screen_id in {"settings", "admin-users"} and not authorization_service.is_superuser(current_user):
        return redirect(url_for("ui.dashboard_page"))
    global_nav_links = [
        {"label": "ダッシュボード", "icon": "bi-house-door", "href": url_for("ui.dashboard_page")},
    ]
    if current_user and getattr(current_user, "role", "user") == "superuser":
        global_nav_links.extend(
            [
                {"label": "ユーザー管理", "icon": "bi-person-gear", "href": url_for("ui.admin_users_page")},
                {"label": "設定", "icon": "bi-sliders", "href": url_for("ui.settings_page")},
            ]
        )
    global_nav_links.extend(
        [
            {"label": "メール", "icon": "bi-envelope-heart", "href": url_for("ui.letters_page")},
            {"label": "Feed", "icon": "bi-broadcast", "href": url_for("ui.feed_page")},
            {"label": "ワールド", "icon": "bi-collection", "href": url_for("ui.project_list_page")},
        ]
    )
    return render_template(
        template_name,
        page_title=title,
        screen_id=screen_id,
        project_id=project_id,
        current_user_id=user_id,
        current_user_display_name=(getattr(current_user, "display_name", None) if current_user else None),
        current_user_email=(getattr(current_user, "email", None) if current_user else None),
        current_user_role=(getattr(current_user, "role", "user") if current_user else None),
        can_manage_project=can_manage_project,
        project_nav_links=_project_nav(project_id, current_user),
        global_nav_links=global_nav_links,
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
    return _render("ui/projects.html", title="ワールド一覧", screen_id="project-list")


@ui_bp.route("/letters", methods=["GET"])
def letters_page():
    return _render("ui/letters.html", title="メール", screen_id="letters")


@ui_bp.route("/feed", methods=["GET"])
def feed_page():
    return _render("ui/feed.html", title="Feed", screen_id="feed")


@ui_bp.route("/projects/new", methods=["GET"])
def project_create_page():
    return _render("ui/project_new.html", title="新規ワールド", screen_id="project-create")


@ui_bp.route("/projects/<int:project_id>/home", methods=["GET"])
def project_home_page(project_id: int):
    return _render("ui/project_home.html", title="ワールドホーム", screen_id="project-home", project_id=project_id)


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


@ui_bp.route("/projects/<int:project_id>/world-map", methods=["GET"])
def world_map_page(project_id: int):
    return _render("ui/world_map.html", title="ワールドマップ", screen_id="world-map", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/outings", methods=["GET"])
def outings_page(project_id: int):
    return _render("ui/outings.html", title="おでかけ", screen_id="outings", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/closet", methods=["GET"])
def closet_page(project_id: int):
    return _render("ui/closet.html", title="クローゼット", screen_id="closet", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/world-news", methods=["GET"])
def world_news_page(project_id: int):
    return _render("ui/world_news.html", title="ワールドニュース", screen_id="world-news", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/stories", methods=["GET"])
def story_list_page(project_id: int):
    return _render("ui/stories.html", title="ストーリー", screen_id="stories", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/stories/new", methods=["GET"])
def story_create_page(project_id: int):
    return _render("ui/story_edit.html", title="ストーリー作成", screen_id="story-edit", project_id=project_id, story_id=None)


@ui_bp.route("/projects/<int:project_id>/stories/<int:story_id>/edit", methods=["GET"])
def story_edit_page(project_id: int, story_id: int):
    return _render("ui/story_edit.html", title="ストーリー編集", screen_id="story-edit", project_id=project_id, story_id=story_id)


@ui_bp.route("/projects/<int:project_id>/story-sessions", methods=["GET"])
def story_session_list_page(project_id: int):
    return _render("ui/story_sessions.html", title="セッション", screen_id="story-sessions", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/story-sessions/<int:session_id>", methods=["GET"])
def story_session_page(project_id: int, session_id: int):
    return _render("ui/story_session.html", title="セッション", screen_id="story-session", project_id=project_id, session_id=session_id)


@ui_bp.route("/projects/<int:project_id>/studio", methods=["GET"])
def studio_page(project_id: int):
    return _render("ui/studio.html", title="スタジオ", screen_id="studio", project_id=project_id)


@ui_bp.route("/projects/<int:project_id>/studio/images/<int:asset_id>", methods=["GET"])
def studio_image_page(project_id: int, asset_id: int):
    return _render("ui/studio_detail.html", title="スタジオ", screen_id="studio", project_id=project_id, asset_id=asset_id)


@ui_bp.route("/projects/<int:project_id>/live-chat", methods=["GET"])
def live_chat_sessions_page(project_id: int):
    return _render(
        "ui/live_chat_sessions.html",
        title="ライブチャット",
        screen_id="live-chat-sessions",
        project_id=project_id,
        manage_mode=False,
    )


@ui_bp.route("/projects/<int:project_id>/live-chat/rooms", methods=["GET"])
def live_chat_rooms_page(project_id: int):
    return _render(
        "ui/live_chat_sessions.html",
        title="ルーム",
        screen_id="live-chat-rooms",
        project_id=project_id,
        manage_mode=True,
    )


@ui_bp.route("/projects/<int:project_id>/live-chat/rooms/new", methods=["GET"])
def live_chat_room_create_page(project_id: int):
    return _render(
        "ui/live_chat_room_edit.html",
        title="ルーム新規追加",
        screen_id="live-chat-room-edit",
        project_id=project_id,
        room_id=None,
    )


@ui_bp.route("/projects/<int:project_id>/live-chat/rooms/<int:room_id>/edit", methods=["GET"])
def live_chat_room_edit_page(project_id: int, room_id: int):
    return _render(
        "ui/live_chat_room_edit.html",
        title="ルーム編集",
        screen_id="live-chat-room-edit",
        project_id=project_id,
        room_id=room_id,
    )


@ui_bp.route("/projects/<int:project_id>/live-chat/<int:session_id>", methods=["GET"])
def live_chat_page(project_id: int, session_id: int):
    return _render(
        "ui/live_chat.html",
        title="ライブチャット",
        screen_id="live-chat",
        project_id=project_id,
        session_id=session_id,
    )


@ui_bp.route("/projects/<int:project_id>/live-chat/<int:session_id>/costumes/new", methods=["GET"])
def live_chat_costume_create_page(project_id: int, session_id: int):
    return redirect(url_for("ui.closet_page", project_id=project_id))


@ui_bp.route("/projects/<int:project_id>/story-sessions/<int:session_id>/costumes/new", methods=["GET"])
def story_session_costume_create_page(project_id: int, session_id: int):
    return redirect(url_for("ui.closet_page", project_id=project_id))


@ui_bp.route("/settings", methods=["GET"])
def settings_page():
    return _render("ui/settings.html", title="設定", screen_id="settings")


@ui_bp.route("/admin/users", methods=["GET"])
def admin_users_page():
    return _render("ui/admin_users.html", title="ユーザー管理", screen_id="admin-users")
