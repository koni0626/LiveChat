from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path


# Edit only this block for quick experiments.
INPUT_IMAGE_PATH = r"C:\Users\konishi\Downloads\live_chat_20260429_075726.png"
OUTPUT_IMAGE_PATH = r"C:\Users\konishi\Downloads\live_chat_20260429_075726out.png"
PROMPT = """参照画像と同じキャラクター性、顔、髪型、色、ノベルゲーム風の画風を維持してください。衣装は変更できます。
半紙でできたコスチューム。
シーン:
夕暮れの海辺で、少し照れた表情でこちらを見つめている。
"""

# Optional knobs. Usually leave these as-is.
PROVIDER = "grok"  # "grok" or "openai"
MODEL = None  # None uses the app default for the provider.
SIZE = "landscape"  # "landscape", "portrait", "square", "1536x1024", etc.
QUALITY = "1k"  # Grok is normalized to 1k by the app client.
NEGATIVE_PROMPT = None
TIMEOUT_SECONDS = None


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.clients.image_ai_client import ImageAIClient  # noqa: E402


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def save_image(result: dict, output_path: Path) -> None:
    image_base64 = result.get("image_base64")
    image_url = result.get("image_url")
    if image_base64:
        output_path.write_bytes(base64.b64decode(image_base64))
        return
    if image_url:
        with urllib.request.urlopen(image_url, timeout=120) as response:
            output_path.write_bytes(response.read())
        return
    raise RuntimeError("Image API response did not include image_base64 or image_url.")


def metadata_for(result: dict, prompt: str, image_path: Path, output_path: Path) -> dict:
    return {
        "input_image": str(image_path),
        "output_image": str(output_path),
        "provider": result.get("provider"),
        "model": result.get("model"),
        "operation": result.get("operation"),
        "size": SIZE,
        "quality": result.get("quality"),
        "aspect_ratio": result.get("aspect_ratio"),
        "reference_image_count": result.get("reference_image_count"),
        "safety_retry": result.get("safety_retry"),
        "prompt_before_safety_retry": result.get("prompt_before_safety_retry"),
        "prompt": prompt,
        "sent_prompt": result.get("prompt"),
        "revised_prompt": result.get("revised_prompt"),
    }


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if TIMEOUT_SECONDS:
        os.environ["IMAGE_AI_TIMEOUT_SECONDS"] = str(TIMEOUT_SECONDS)

    image_path = Path(INPUT_IMAGE_PATH).expanduser().resolve()
    output_path = Path(OUTPUT_IMAGE_PATH).expanduser().resolve()
    prompt = PROMPT.strip()

    if not image_path.exists():
        raise FileNotFoundError(f"INPUT_IMAGE_PATH does not exist: {image_path}")
    if not prompt:
        raise ValueError("PROMPT is empty.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = output_path.with_suffix(".json")
    if output_path.exists():
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = output_path.with_name(f"{output_path.stem}_{stamp}{output_path.suffix}")
        output_path = backup_path
        metadata_path = output_path.with_suffix(".json")

    client = ImageAIClient(provider=PROVIDER)
    print(f"Generating with provider={PROVIDER}, model={MODEL or '(default)'}, size={SIZE}")
    print(f"Input: {image_path}")
    print(f"Output: {output_path}")

    result = client.generate_image(
        prompt,
        provider=PROVIDER,
        model=MODEL,
        size=SIZE,
        quality=QUALITY,
        negative_prompt=NEGATIVE_PROMPT,
        input_image_paths=[str(image_path)],
        output_format="png",
        input_fidelity="high",
    )

    save_image(result, output_path)
    metadata_path.write_text(
        json.dumps(metadata_for(result, prompt, image_path, output_path), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved image: {output_path}")
    print(f"Saved metadata: {metadata_path}")
    if result.get("safety_retry"):
        print("Safety retry was used. See prompt_before_safety_retry in metadata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
