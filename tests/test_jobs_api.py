from app.extensions import db
from app.models import ExportJob, GenerationJob, User, Project


def _create_project():
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
    db.session.commit()
    return project


def test_get_generation_job_returns_progress(app, client):
    with app.app_context():
        project = _create_project()
        job = GenerationJob(
            project_id=project.id,
            job_type="text_generation",
            target_type="scene",
            target_id=10,
            status="running",
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id

    response = client.get(f"/api/v1/jobs/{job_id}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["kind"] == "generation"
    assert payload["data"]["status"] == "running"
    assert payload["data"]["progress"] == 50


def test_get_export_job_returns_progress(app, client):
    with app.app_context():
        project = _create_project()
        job = ExportJob(
            project_id=project.id,
            export_type="json",
            status="success",
        )
        db.session.add(job)
        db.session.commit()
        job_id = job.id

    response = client.get(f"/api/v1/jobs/{job_id}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"]["kind"] == "export"
    assert payload["data"]["status"] == "success"
    assert payload["data"]["progress"] == 100
