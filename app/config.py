import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def load_env_file(env_path: str | None = None, *, override: bool = False) -> None:
    path = env_path or os.path.join(PROJECT_ROOT, ".env")
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].strip()
            if "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = _strip_wrapping_quotes(value.strip())
            if not key:
                continue
            if override or key not in os.environ:
                os.environ[key] = value


load_env_file()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    REQUIRE_STRONG_SECRET_KEY = os.getenv("REQUIRE_STRONG_SECRET_KEY", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(PROJECT_ROOT, "instance", "app.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    SESSION_TYPE = "sqlalchemy"
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    CSRF_ENABLED = os.getenv("CSRF_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    STORAGE_ROOT = os.getenv("STORAGE_ROOT", os.path.join(PROJECT_ROOT, "storage"))
    TEXT_AI_MODEL = os.getenv("TEXT_AI_MODEL", "gpt-5.4-mini")
    IMAGE_AI_PROVIDER = os.getenv("IMAGE_AI_PROVIDER", "openai")
    IMAGE_AI_MODEL = os.getenv("IMAGE_AI_MODEL", "gpt-image-2")
    XAI_IMAGE_MODEL = os.getenv("XAI_IMAGE_MODEL", "grok-imagine-image")
    IMAGE_DEFAULT_QUALITY = os.getenv("IMAGE_DEFAULT_QUALITY", "medium")
    TEXT_AI_TIMEOUT_SECONDS = int(os.getenv("TEXT_AI_TIMEOUT_SECONDS", "120"))
    IMAGE_AI_TIMEOUT_SECONDS = int(os.getenv("IMAGE_AI_TIMEOUT_SECONDS", "60"))
    LETTER_COOLDOWN_MINUTES = int(os.getenv("LETTER_COOLDOWN_MINUTES", "360"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", str(12 * 1024 * 1024)))
    ASSET_MAX_UPLOAD_BYTES = int(os.getenv("ASSET_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    ASSET_ALLOWED_IMAGE_MIME_TYPES = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
    }
    AUTH_RATE_LIMIT_ATTEMPTS = int(os.getenv("AUTH_RATE_LIMIT_ATTEMPTS", "10"))
    AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "900"))
    LIVE_CHAT_DEFER_POST_PROCESSING = os.getenv("LIVE_CHAT_DEFER_POST_PROCESSING", "false").lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
