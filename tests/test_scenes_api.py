from app.extensions import db
from app.models import Chapter, Project, Scene, User


def _create_project_graph():
    user = User(
        email="owner@example.com",
        display_name="owner",
        password_hash="dummy",
        status="active",
    )
    db.session.add(user)
    db.session.flush()

    project = Project(
        owner_user_id=user.id,
        title="Test Project",
        genre="SF",
        project_type="exploration",
        status="draft",
    )
    db.session.add(project)
    db.session.flush()

    chapter = Chapter(
        project_id=project.id,
        chapter_no=1,
        title="Chapter 1",
        sort_order=1,
    )
    db.session.add(chapter)
    db.session.flush()

    scene = Scene(
        project_id=project.id,
        chapter_id=chapter.id,
        title="Scene 1",
        sort_order=1,
    )
    db.session.add(scene)
    db.session.commit()

    return {"user": user, "project": project, "chapter": chapter, "scene": scene}


def test_scene_generate_endpoint_creates_generation_job(app, client):
    with app.app_context():
        graph = _create_project_graph()
        scene_id = graph["scene"].id

    response = client.post(
        f"/api/v1/scenes/{scene_id}/generate",
        json={"mode": "next_scene", "choice_count": 3},
    )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload["data"]["job_type"] == "text_generation"
    assert payload["data"]["status"] == "queued"
    assert payload["data"]["target_id"] == scene_id


def test_scene_extract_state_endpoint_creates_generation_job(app, client):
    with app.app_context():
        graph = _create_project_graph()
        scene_id = graph["scene"].id

    response = client.post(
        f"/api/v1/scenes/{scene_id}/extract-state",
        json={"source": "current_scene"},
    )

    assert response.status_code == 202
    payload = response.get_json()
    assert payload["data"]["job_type"] == "state_extraction"
    assert payload["data"]["status"] == "queued"
    assert payload["data"]["target_id"] == scene_id


def test_scene_fix_and_unfix_endpoints_toggle_state(app, client):
    with app.app_context():
        graph = _create_project_graph()
        scene_id = graph["scene"].id

    fix_response = client.post(f"/api/v1/scenes/{scene_id}/fix")
    assert fix_response.status_code == 200
    assert fix_response.get_json()["data"]["is_fixed"] is True

    unfix_response = client.post(f"/api/v1/scenes/{scene_id}/unfix")
    assert unfix_response.status_code == 200
    assert unfix_response.get_json()["data"]["is_fixed"] is False
