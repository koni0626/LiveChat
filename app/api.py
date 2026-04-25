from __future__ import annotations

from flask import jsonify


class ApiError(Exception):
    def __init__(self, message: str, *, status_code: int, code: str, meta: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.meta = meta or {}


class ValidationError(ApiError):
    def __init__(self, message: str, *, code: str = "bad_request", meta: dict | None = None):
        super().__init__(message, status_code=400, code=code, meta=meta)


class UnauthorizedError(ApiError):
    def __init__(self, message: str = "unauthorized", *, code: str = "unauthorized", meta: dict | None = None):
        super().__init__(message, status_code=401, code=code, meta=meta)


class ForbiddenError(ApiError):
    def __init__(self, message: str = "forbidden", *, code: str = "forbidden", meta: dict | None = None):
        super().__init__(message, status_code=403, code=code, meta=meta)


class NotFoundError(ApiError):
    def __init__(self, message: str = "not_found", *, code: str = "not_found", meta: dict | None = None):
        super().__init__(message, status_code=404, code=code, meta=meta)


class UnprocessableEntityError(ApiError):
    def __init__(
        self,
        message: str = "unprocessable_entity",
        *,
        code: str = "unprocessable_entity",
        meta: dict | None = None,
    ):
        super().__init__(message, status_code=422, code=code, meta=meta)


def json_response(data, status: int = 200, meta: dict | None = None):
    return jsonify({"data": data, "meta": meta or {}}), status


def error_response(message: str, *, status: int, code: str, meta: dict | None = None):
    return json_response({"message": message, "code": code}, status=status, meta=meta)


def serialize_datetime(value):
    return value.isoformat() if value is not None else None


def require_found(value, message: str = "not_found"):
    if value is None:
        raise NotFoundError(message)
    return value
