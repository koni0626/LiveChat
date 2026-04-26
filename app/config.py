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
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(PROJECT_ROOT, "instance", "app.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    SESSION_TYPE = "sqlalchemy"
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    STORAGE_ROOT = os.getenv("STORAGE_ROOT", os.path.join(PROJECT_ROOT, "storage"))
    TEXT_AI_MODEL = os.getenv("TEXT_AI_MODEL", "gpt-5.4-mini")
    IMAGE_AI_MODEL = os.getenv("IMAGE_AI_MODEL", "gpt-image-2")
    TEXT_AI_TIMEOUT_SECONDS = int(os.getenv("TEXT_AI_TIMEOUT_SECONDS", "120"))
    IMAGE_AI_TIMEOUT_SECONDS = int(os.getenv("IMAGE_AI_TIMEOUT_SECONDS", "60"))
    LETTER_COOLDOWN_MINUTES = int(os.getenv("LETTER_COOLDOWN_MINUTES", "360"))
