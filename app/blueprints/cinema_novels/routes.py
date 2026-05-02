import threading
import uuid
from datetime import datetime

from flask import Blueprint, current_app, request, session

from ...api import ForbiddenError, NotFoundError, UnauthorizedError, ValidationError, json_response
from ...models import User
from ...services.authorization_service import AuthorizationService
from ...services.cinema_novel_service import CinemaNovelService
from ...services.project_service import ProjectService


cinema_novels_bp = Blueprint("cinema_novels", __name__)
authorization_service = AuthorizationService()
project_service = ProjectService()
cinema_novel_service = CinemaNovelService()
production_outline_jobs = {}
production_outline_jobs_lock = threading.Lock()


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        raise UnauthorizedError()
    user = User.query.get(user_id)
    if not user or not user.is_active_user:
        raise UnauthorizedError()
    return user


def _require_project(project_id: int, *, for_manage: bool = False):
    user = _current_user()
    project = project_service.get_project(project_id)
    if not project:
        raise NotFoundError()
    if for_manage and not authorization_service.can_manage_project(user, project):
        raise ForbiddenError()
    if not for_manage and not authorization_service.can_view_project(user, project):
        raise NotFoundError()
    return project, user


def _require_novel(novel_id: int, *, for_manage: bool = False):
    user = _current_user()
    novel = cinema_novel_service.get_novel(novel_id)
    if not novel:
        raise NotFoundError()
    project = project_service.get_project(novel.project_id)
    if not project:
        raise NotFoundError()
    if for_manage:
        if not authorization_service.can_manage_project(user, project):
            raise ForbiddenError()
    elif not authorization_service.can_view_project(user, project):
        raise NotFoundError()
    return novel, project, user


@cinema_novels_bp.route("/projects/<int:project_id>/cinema-novels", methods=["GET"])
def list_project_cinema_novels(project_id: int):
    project, user = _require_project(project_id)
    include_unpublished = authorization_service.can_manage_project(user, project)
    novels = cinema_novel_service.list_novels(project_id, include_unpublished=include_unpublished)
    return json_response([cinema_novel_service.serialize_novel(novel, user_id=user.id) for novel in novels])


@cinema_novels_bp.route("/projects/<int:project_id>/cinema-novels/import-markdown-folder", methods=["POST"])
def import_markdown_folder(project_id: int):
    _, user = _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        novel = cinema_novel_service.import_markdown_folder(project_id, user.id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    return json_response(cinema_novel_service.serialize_novel(novel, include_chapters=True, user_id=user.id), status=201)


@cinema_novels_bp.route("/projects/<int:project_id>/cinema-novels/production-outline", methods=["POST"])
def generate_production_outline(project_id: int):
    _project, _user = _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        result = cinema_novel_service.generate_production_outline(project_id, payload)
    except (RuntimeError, ValueError) as exc:
        raise ValidationError(str(exc))
    return json_response(result, status=201)


@cinema_novels_bp.route("/projects/<int:project_id>/cinema-novels/production-premise", methods=["POST"])
def generate_production_premise(project_id: int):
    _project, _user = _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        result = cinema_novel_service.generate_production_premise(project_id, payload)
    except (RuntimeError, ValueError) as exc:
        raise ValidationError(str(exc))
    return json_response(result, status=201)


@cinema_novels_bp.route("/projects/<int:project_id>/cinema-novels/production-outline/save", methods=["POST"])
def save_production_outline(project_id: int):
    _project, user = _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        novel = cinema_novel_service.save_production_outline(project_id, user.id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    return json_response(cinema_novel_service.serialize_novel(novel, include_chapters=True, user_id=user.id), status=201)


def _serialize_production_outline_job(job: dict):
    return {
        "id": job.get("id"),
        "project_id": job.get("project_id"),
        "status": job.get("status"),
        "result": job.get("result"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
    }


@cinema_novels_bp.route("/projects/<int:project_id>/cinema-novels/production-outline-jobs", methods=["POST"])
def create_production_outline_job(project_id: int):
    _project, _user = _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    job_id = uuid.uuid4().hex
    job = {
        "id": job_id,
        "project_id": project_id,
        "status": "queued",
        "payload": payload,
        "result": None,
        "error": None,
        "created_at": datetime.utcnow().isoformat(),
        "started_at": None,
        "finished_at": None,
    }
    with production_outline_jobs_lock:
        production_outline_jobs[job_id] = job

    app = current_app._get_current_object()

    def worker():
        with app.app_context():
            with production_outline_jobs_lock:
                job["status"] = "running"
                job["started_at"] = datetime.utcnow().isoformat()
            try:
                result = cinema_novel_service.generate_production_outline(project_id, payload)
                with production_outline_jobs_lock:
                    job["status"] = "succeeded"
                    job["result"] = result
                    job["finished_at"] = datetime.utcnow().isoformat()
            except Exception as exc:
                app.logger.exception("cinema novel production outline job failed")
                with production_outline_jobs_lock:
                    job["status"] = "failed"
                    job["error"] = str(exc)
                    job["finished_at"] = datetime.utcnow().isoformat()
            finally:
                try:
                    from ...extensions import db

                    db.session.remove()
                except Exception:
                    pass

    threading.Thread(target=worker, name=f"cinema-outline-{job_id}", daemon=True).start()
    return json_response(_serialize_production_outline_job(job), status=202)


@cinema_novels_bp.route("/projects/<int:project_id>/cinema-novels/production-outline-jobs/<job_id>", methods=["GET"])
def get_production_outline_job(project_id: int, job_id: str):
    _project, _user = _require_project(project_id, for_manage=True)
    with production_outline_jobs_lock:
        job = production_outline_jobs.get(job_id)
        if not job or int(job.get("project_id") or 0) != int(project_id):
            raise NotFoundError()
        return json_response(_serialize_production_outline_job(dict(job)))


@cinema_novels_bp.route("/projects/<int:project_id>/cinema-novels/chapter-deepening-draft", methods=["POST"])
def generate_chapter_deepening_draft(project_id: int):
    _project, _user = _require_project(project_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        result = cinema_novel_service.generate_chapter_deepening_draft(payload)
    except (RuntimeError, ValueError) as exc:
        raise ValidationError(str(exc))
    return json_response(result, status=201)


@cinema_novels_bp.route("/cinema-novels/<int:novel_id>", methods=["GET"])
def get_cinema_novel(novel_id: int):
    novel, _, user = _require_novel(novel_id)
    return json_response(cinema_novel_service.serialize_novel(novel, include_chapters=True, user_id=user.id))


@cinema_novels_bp.route("/cinema-novels/<int:novel_id>/chapters/from-production-outline", methods=["POST"])
def create_chapters_from_production_outline(novel_id: int):
    novel, _project, user = _require_novel(novel_id, for_manage=True)
    try:
        cinema_novel_service.create_chapters_from_production_outline(novel.id)
    except ValueError as exc:
        raise ValidationError(str(exc))
    return json_response(cinema_novel_service.serialize_novel(novel, include_chapters=True, user_id=user.id), status=201)


@cinema_novels_bp.route("/cinema-novels/<int:novel_id>/title-image", methods=["POST"])
def generate_cinema_novel_title_image(novel_id: int):
    _novel, _project, _user = _require_novel(novel_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        result = cinema_novel_service.generate_title_image(novel_id, payload)
    except (RuntimeError, ValueError) as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@cinema_novels_bp.route("/cinema-novels/<int:novel_id>/chapters/<int:chapter_id>", methods=["PUT"])
def update_cinema_novel_chapter(novel_id: int, chapter_id: int):
    _novel, _project, _user = _require_novel(novel_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        chapter = cinema_novel_service.update_chapter_markdown(novel_id, chapter_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not chapter:
        raise NotFoundError()
    return json_response(cinema_novel_service.serialize_chapter(chapter))


@cinema_novels_bp.route("/cinema-novels/<int:novel_id>/chapters/<int:chapter_id>/deepen", methods=["POST"])
def deepen_cinema_novel_chapter(novel_id: int, chapter_id: int):
    _novel, _project, _user = _require_novel(novel_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        result = cinema_novel_service.generate_chapter_deepening_for_chapter(novel_id, chapter_id, payload)
    except (RuntimeError, ValueError) as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@cinema_novels_bp.route("/cinema-novels/<int:novel_id>/chapters/<int:chapter_id>/image-plan", methods=["POST"])
def generate_cinema_novel_chapter_image_plan(novel_id: int, chapter_id: int):
    _novel, _project, _user = _require_novel(novel_id, for_manage=True)
    result = cinema_novel_service.generate_chapter_image_plan(novel_id, chapter_id)
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@cinema_novels_bp.route("/cinema-novels/<int:novel_id>/chapters/<int:chapter_id>/images", methods=["POST"])
def generate_cinema_novel_chapter_images(novel_id: int, chapter_id: int):
    _novel, _project, _user = _require_novel(novel_id, for_manage=True)
    payload = request.get_json(silent=True) or {}
    try:
        result = cinema_novel_service.generate_chapter_images(novel_id, chapter_id, payload)
    except (RuntimeError, ValueError) as exc:
        raise ValidationError(str(exc))
    if not result:
        raise NotFoundError()
    return json_response(result, status=201)


@cinema_novels_bp.route("/cinema-novels/<int:novel_id>/progress", methods=["PUT"])
def save_cinema_novel_progress(novel_id: int):
    _novel, _project, user = _require_novel(novel_id)
    payload = request.get_json(silent=True) or {}
    try:
        progress = cinema_novel_service.save_progress(user.id, novel_id, payload)
    except ValueError as exc:
        raise ValidationError(str(exc))
    if not progress:
        raise NotFoundError()
    return json_response(cinema_novel_service.serialize_progress(progress))
