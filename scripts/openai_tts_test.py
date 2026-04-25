from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


DEFAULT_TEXT = "こんにちは、ラプラスです。これはテストです。"
#DEFAULT_INSTRUCTIONS = "明るく柔らかい日本語の女性キャラクターとして、親しげに話してください。"
DEFAULT_INSTRUCTIONS = "セリフだけを読むのではなく、恋愛ノベルゲームのヒロインのように演技してください。語尾に少し余韻を残し、嬉しさを含んだ柔らかい声で、少し照れながら話してください。抑揚を大きめに、間を自然に入れてください。"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def create_speech(
    *,
    api_key: str,
    text: str,
    output_path: Path,
    model: str,
    voice: str,
    instructions: str,
    response_format: str,
) -> None:
    payload = {
        "model": model,
        "voice": voice,
        "input": text,
        "response_format": response_format,
    }
    if instructions:
        payload["instructions"] = instructions

    request = urllib.request.Request(
        "https://api.openai.com/v1/audio/speech",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI TTS request failed ({exc.code}): {body}") from exc


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")

    parser = argparse.ArgumentParser(description="Generate a short OpenAI TTS test audio file.")
    parser.add_argument("--text", default=DEFAULT_TEXT)
    parser.add_argument("--instructions", default=DEFAULT_INSTRUCTIONS)
    parser.add_argument("--model", default=os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"))
    parser.add_argument("--voice", default=os.environ.get("OPENAI_TTS_VOICE", "nova"))
    parser.add_argument("--format", default="mp3", choices=["mp3", "opus", "aac", "flac", "wav", "pcm"])
    parser.add_argument("--output", default=str(project_root / "storage" / "tts_tests" / "laplace_test.mp3"))
    parser.add_argument("--play", action="store_true", help="Open the generated audio file with the default player.")
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-your-api-key"):
        print("OPENAI_API_KEY が未設定です。.env に実キーを設定してください。", file=sys.stderr)
        return 2

    output_path = Path(args.output)
    create_speech(
        api_key=api_key,
        text=args.text,
        output_path=output_path,
        model=args.model,
        voice=args.voice,
        instructions=args.instructions,
        response_format=args.format,
    )
    print(f"created: {output_path}")

    if args.play:
        os.startfile(output_path)  # type: ignore[attr-defined]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
