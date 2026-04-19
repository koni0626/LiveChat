from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_env_file  # noqa: E402


def _print_block(title: str, value) -> None:
    print(f"\n[{title}]")
    if isinstance(value, (dict, list)):
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify whether gpt-image-1.5 works with /v1/images/generations and /v1/images/edits."
    )
    parser.add_argument("--env-file", default=str(PROJECT_ROOT / ".env"))
    parser.add_argument("--image", help="Absolute or relative path to a reference image for /images/edits.")
    parser.add_argument(
        "--prompt",
        default="A clean anime-style character portrait, looking at the camera, soft lighting.",
    )
    parser.add_argument("--size", default="1024x1024")
    parser.add_argument("--model", default=os.getenv("IMAGE_AI_MODEL") or "gpt-image-1.5")
    return parser.parse_args()


def _load_env(env_file: str) -> None:
    if env_file:
        load_env_file(env_file, override=False)


def _api_key() -> str:
    value = os.getenv("OPENAI_API_KEY", "").strip()
    if not value:
        raise SystemExit("OPENAI_API_KEY is not set. Put it in .env or pass it in the environment.")
    return value


def _request_generations(api_key: str, *, prompt: str, size: str, model: str) -> None:
    payload = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": "b64_json",
    }
    response = requests.post(
        "https://api.openai.com/v1/images/generations",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    _print_block("generations request", payload)
    _print_block("generations status", response.status_code)
    try:
        _print_block("generations response", response.json())
    except ValueError:
        _print_block("generations response", response.text)


def _request_edits(api_key: str, *, prompt: str, size: str, model: str, image_path: Path) -> None:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    data = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": "b64_json",
    }
    with image_path.open("rb") as image_file:
        response = requests.post(
            "https://api.openai.com/v1/images/edits",
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files=[("image[]", (image_path.name, image_file, mime_type))],
            timeout=120,
        )
    _print_block("edits request", {**data, "image_path": str(image_path), "mime_type": mime_type})
    _print_block("edits status", response.status_code)
    try:
        _print_block("edits response", response.json())
    except ValueError:
        _print_block("edits response", response.text)


def main() -> None:
    args = _parse_args()
    _load_env(args.env_file)
    api_key = _api_key()

    _print_block("environment", {"env_file": args.env_file, "model": args.model, "size": args.size})
    _request_generations(api_key, prompt=args.prompt, size=args.size, model=args.model)

    if args.image:
        image_path = Path(args.image).expanduser()
        if not image_path.is_absolute():
            image_path = (PROJECT_ROOT / image_path).resolve()
        if not image_path.exists():
            raise SystemExit(f"reference image not found: {image_path}")
        _request_edits(api_key, prompt=args.prompt, size=args.size, model=args.model, image_path=image_path)
    else:
        _print_block("edits", "skipped (pass --image to test /v1/images/edits)")


if __name__ == "__main__":
    main()
