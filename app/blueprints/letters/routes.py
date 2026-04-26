from flask import Blueprint, session

from ...api import NotFoundError, UnauthorizedError, json_response
from ...models import User
from ...services.letter_service import LetterService


letters_bp = Blueprint("letters", __name__)
letter_service = LetterService()


def _current_user():
    user_id = session.get("user_id")
    if not user_id:
        raise UnauthorizedError()
    user = User.query.get(user_id)
    if not user or not user.is_active_user:
        raise UnauthorizedError()
    return user


@letters_bp.route("/letters", methods=["GET"])
def list_letters():
    user = _current_user()
    return json_response(
        letter_service.list_for_user(user.id),
        meta={"unread_count": letter_service.unread_count(user.id)},
    )


@letters_bp.route("/letters/unread-count", methods=["GET"])
def count_unread_letters():
    user = _current_user()
    return json_response({"unread_count": letter_service.unread_count(user.id)})


@letters_bp.route("/letters/<int:letter_id>", methods=["GET"])
def get_letter(letter_id: int):
    user = _current_user()
    letter = letter_service.get_for_user(letter_id, user.id)
    if not letter:
        raise NotFoundError()
    return json_response(letter)


@letters_bp.route("/letters/<int:letter_id>/read", methods=["POST"])
def mark_letter_read(letter_id: int):
    user = _current_user()
    letter = letter_service.mark_read_for_user(letter_id, user.id)
    if not letter:
        raise NotFoundError()
    return json_response(letter)


@letters_bp.route("/letters/<int:letter_id>", methods=["DELETE"])
def archive_letter(letter_id: int):
    user = _current_user()
    letter = letter_service.archive_for_user(letter_id, user.id)
    if not letter:
        raise NotFoundError()
    return json_response(letter)
