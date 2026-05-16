from __future__ import annotations

import argparse
import base64
import json
import os
from datetime import datetime
from pathlib import Path

from app import create_app
from app.clients.image_ai_client import ImageAIClient
from app.services.x_publishing_service import XPublishingService


FIXED_HASHTAG = "#ラプラスシティ"
DEFAULT_HASHTAGS = [FIXED_HASHTAG, "#小説"]


def _read_package(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as file_handle:
        payload = json.load(file_handle)
    if not isinstance(payload, dict):
        raise ValueError("package root must be an object")
    return payload


def _write_package(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")


def _hashtags(payload: dict) -> list[str]:
    value = payload.get("hashtags")
    if value is None or value == "auto":
        return _suggest_hashtags(payload)
    if isinstance(value, str):
        tags = [tag for tag in value.split() if tag.startswith("#")]
        return _dedupe_hashtags([FIXED_HASHTAG, *tags])
    return _dedupe_hashtags([FIXED_HASHTAG, *[str(tag).strip() for tag in value if str(tag).strip()]])


def _dedupe_hashtags(tags: list[str], *, limit: int = 4) -> list[str]:
    normalized = []
    seen = set()
    for tag in tags:
        value = str(tag or "").strip()
        if not value:
            continue
        if not value.startswith("#"):
            value = f"#{value}"
        key = value.casefold()
        if key in seen:
            continue
        normalized.append(value)
        seen.add(key)
    if FIXED_HASHTAG not in normalized:
        normalized.insert(0, FIXED_HASHTAG)
    return normalized[: max(1, limit)]


def _suggest_hashtags(payload: dict) -> list[str]:
    haystack = "\n".join(
        [
            str(payload.get("title") or ""),
            str(payload.get("source") or ""),
            "\n".join(str(post.get("text") or "") for post in payload.get("posts") or []),
        ]
    )
    tags = [FIXED_HASHTAG]
    character = str(payload.get("character") or payload.get("character_name") or "").strip()
    if character:
        tags.append(f"#{character}のブログ")
    elif "ノア" in haystack and any(word in haystack for word in ("ブログ", "記事", "思います", "フーコー", "静かな解雇")):
        tags.append("#ノアのブログ")
    elif "ラプ" in haystack and any(word in haystack for word in ("ブログ", "記事", "ですわ")):
        tags.append("#ラプのブログ")

    if any(word in haystack for word in ("第1話", "第2話", "第3話", "小説", "物語", "episode", "novel")):
        tags.append("#小説")
    if any(word in haystack for word in ("AI", "生成AI", "人工知能")):
        tags.append("#AI")
    if any(word in haystack for word in ("仕事", "会社", "解雇", "退職", "働き方", "新人", "管理職")):
        tags.append("#働き方")
    if any(word in haystack for word in ("創作", "世界観", "キャラクター")):
        tags.append("#創作")
    return _dedupe_hashtags(tags)


def _append_hashtags(posts: list[dict], hashtags: list[str]) -> list[dict]:
    normalized = [dict(post) for post in posts]
    if not normalized or not hashtags:
        return normalized
    suffix = " ".join(hashtags)
    last = normalized[-1]
    text = str(last.get("text") or "").rstrip()
    if suffix not in text:
        last["text"] = f"{text}\n\n{suffix}" if text else suffix
    return normalized


def _image_paths(posts: list[dict]) -> list[str]:
    paths = []
    for post in posts:
        for key in ("image_path", "image"):
            value = post.get(key)
            if value:
                paths.append(os.path.abspath(str(value)))
        for value in post.get("image_paths") or []:
            if value:
                paths.append(os.path.abspath(str(value)))
    return sorted(set(paths))


def _posts_for_preview(payload: dict, service: XPublishingService) -> list[dict]:
    posts = payload.get("posts") or []
    if not isinstance(posts, list) or not posts:
        raise ValueError("package must contain a non-empty posts array")
    posts = _append_hashtags(posts, _hashtags(payload))
    rendered = []
    for source_index, post in enumerate(posts, start=1):
        text = str(post.get("text") or "")
        images = []
        for key in ("image_path", "image"):
            if post.get(key):
                images.append(os.path.abspath(str(post[key])))
        images.extend(os.path.abspath(str(path)) for path in post.get("image_paths") or [] if path)
        parts = service.split_thread(text)
        for split_index, part in enumerate(parts, start=1):
            rendered.append(
                {
                    "source_index": source_index,
                    "split_index": split_index,
                    "text": part,
                    "weight": service._tweet_weight(part),
                    "images": images if split_index == 1 else [],
                    "image_prompt": str(post.get("image_prompt") or "") if split_index == 1 else "",
                    "reference_images": [os.path.abspath(str(path)) for path in post.get("reference_images") or []]
                    if split_index == 1
                    else [],
                }
            )
    return rendered


def _markdown_image(path: str) -> str:
    normalized = path.replace("\\", "/")
    return f"![thread image]({normalized})"


def command_preview(args) -> None:
    payload = _read_package(Path(args.package))
    service = XPublishingService()
    rendered_posts = _posts_for_preview(payload, service)
    title = str(payload.get("title") or Path(args.package).stem)
    lines = [
        f"# X Thread Preview: {title}",
        "",
        f"- Package: `{Path(args.package).resolve()}`",
        f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"- Posts after split: {len(rendered_posts)}",
        f"- Hashtags: {' '.join(_hashtags(payload)) or '(none)'}",
        "",
    ]
    for index, post in enumerate(rendered_posts, start=1):
        lines.extend(
            [
                f"## Post {index}/{len(rendered_posts)}",
                "",
                f"- Weighted length: {post['weight']}/{service.TWEET_WEIGHT_LIMIT}",
                f"- Source item: {post['source_index']}",
                "",
                "```text",
                post["text"],
                "```",
                "",
            ]
        )
        for image_path in post["images"]:
            lines.extend([_markdown_image(image_path), ""])
        if post["image_prompt"]:
            lines.extend(["### Image Prompt", "", "```text", post["image_prompt"], "```", ""])
        if post["reference_images"]:
            lines.extend(["### Reference Images", ""])
            for reference_path in post["reference_images"]:
                lines.extend([_markdown_image(reference_path), ""])
    out_path = Path(args.out) if args.out else Path(args.package).with_suffix(".preview.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(str(out_path.resolve()))


def command_new(args) -> None:
    payload = {
        "title": args.title,
        "hashtags": list(DEFAULT_HASHTAGS),
        "posts": [
            {
                "text": args.text or "ここに1ポスト目の本文を書く",
                "image_path": args.image or "",
            }
        ],
    }
    _write_package(Path(args.out), payload)
    print(str(Path(args.out).resolve()))


def _save_generated_image(package_path: Path, post_index: int, image_base64: str) -> str:
    raw = base64.b64decode(image_base64)
    output_dir = package_path.parent / "images" / package_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"post_{post_index:02d}_{stamp}.png"
    output_path.write_bytes(raw)
    return str(output_path.resolve())


def _looks_like_mojibake_prompt(prompt: str) -> bool:
    text = str(prompt or "").strip()
    if not text:
        return False
    question_ratio = text.count("?") / max(1, len(text))
    cjk_count = sum(1 for char in text if "\u3040" <= char <= "\u30ff" or "\u4e00" <= char <= "\u9fff")
    return question_ratio > 0.2 and cjk_count < 12


def command_generate_images(args) -> None:
    package_path = Path(args.package)
    payload = _read_package(package_path)
    posts = payload.get("posts") or []
    if not isinstance(posts, list) or not posts:
        raise ValueError("package must contain a non-empty posts array")
    previous_safety_mode = os.environ.get("IMAGE_PROMPT_SAFETY_MODE")
    if args.no_grok_fallback:
        os.environ["IMAGE_PROMPT_SAFETY_MODE"] = "off"
    client = ImageAIClient(provider=args.provider or None)
    generated = 0
    try:
        for index, post in enumerate(posts, start=1):
            if args.post and index != int(args.post):
                continue
            prompt = str(post.get("image_prompt") or "").strip()
            if not prompt:
                continue
            if _looks_like_mojibake_prompt(prompt):
                raise ValueError(
                    f"post {index} image_prompt looks corrupted by encoding conversion. "
                    "Refusing to spend image API credits."
                )
            if post.get("image_path") and not args.overwrite:
                continue
            reference_images = [str(path) for path in post.get("reference_images") or [] if str(path).strip()]
            last_error = None
            result = None
            for attempt in range(1, max(1, int(args.attempts or 1)) + 1):
                try:
                    result = client.generate_image(
                        prompt,
                        size=args.size,
                        quality=args.quality,
                        input_image_paths=reference_images,
                        input_fidelity="high" if reference_images else None,
                        provider=args.provider or None,
                    )
                    if args.no_grok_fallback and result.get("provider") == "grok":
                        raise RuntimeError("grok fallback was used despite --no-grok-fallback")
                    break
                except Exception as exc:
                    last_error = exc
                    print(f"post {index} image generation attempt {attempt} failed: {exc}")
                    if attempt >= max(1, int(args.attempts or 1)):
                        raise
            if result is None:
                raise RuntimeError(f"post {index} image generation failed") from last_error
            image_base64 = result.get("image_base64")
            if not image_base64:
                raise RuntimeError(f"post {index} image generation response did not include image_base64")
            post["image_path"] = _save_generated_image(package_path, index, image_base64)
            metadata = dict(post.get("image_generation") or {})
            metadata.update(
                {
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "provider": result.get("provider"),
                    "model": result.get("model"),
                    "reference_image_count": result.get("reference_image_count"),
                    "operation": result.get("operation"),
                }
            )
            post["image_generation"] = metadata
            generated += 1
            print(f"generated post {index}: {post['image_path']}")
    finally:
        if args.no_grok_fallback:
            if previous_safety_mode is None:
                os.environ.pop("IMAGE_PROMPT_SAFETY_MODE", None)
            else:
                os.environ["IMAGE_PROMPT_SAFETY_MODE"] = previous_safety_mode
    payload["posts"] = posts
    _write_package(package_path, payload)
    print(f"updated {package_path.resolve()} ({generated} generated)")


def _posts_for_publish(payload: dict, service: XPublishingService) -> list[dict]:
    posts = _append_hashtags(payload.get("posts") or [], _hashtags(payload))
    uploaded = service.upload_media_paths(_image_paths(posts))
    prepared = []
    for post in posts:
        image_paths = []
        for key in ("image_path", "image"):
            if post.get(key):
                image_paths.append(os.path.abspath(str(post[key])))
        image_paths.extend(os.path.abspath(str(path)) for path in post.get("image_paths") or [] if path)
        prepared.append(
            {
                "text": str(post.get("text") or ""),
                "media_ids": [uploaded[path] for path in image_paths if path in uploaded],
            }
        )
    return prepared


def command_publish(args) -> None:
    if not args.yes:
        raise SystemExit("Refusing to publish without --yes. Run preview first, then pass --yes.")
    payload = _read_package(Path(args.package))
    app = create_app()
    with app.app_context():
        service = XPublishingService()
        prepared_posts = _posts_for_publish(payload, service)
        result = service.publish_thread_posts(prepared_posts)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build, preview, and publish X thread packages.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_parser = subparsers.add_parser("new", help="Create a starter package JSON.")
    new_parser.add_argument("--out", required=True)
    new_parser.add_argument("--title", default="ラプラスシティ投稿")
    new_parser.add_argument("--text", default="")
    new_parser.add_argument("--image", default="")
    new_parser.set_defaults(func=command_new)

    preview_parser = subparsers.add_parser("preview", help="Render a package as Markdown.")
    preview_parser.add_argument("package")
    preview_parser.add_argument("--out", default="")
    preview_parser.set_defaults(func=command_preview)

    image_parser = subparsers.add_parser("generate-images", help="Generate missing images for posts with image_prompt.")
    image_parser.add_argument("package")
    image_parser.add_argument("--overwrite", action="store_true")
    image_parser.add_argument("--provider", default="")
    image_parser.add_argument("--size", default="1536x1024")
    image_parser.add_argument("--quality", default="medium")
    image_parser.add_argument("--post", type=int, default=0, help="Generate only the 1-based post index.")
    image_parser.add_argument("--attempts", type=int, default=2)
    image_parser.add_argument("--no-grok-fallback", action="store_true")
    image_parser.set_defaults(func=command_generate_images)

    publish_parser = subparsers.add_parser("publish", help="Publish a package to X.")
    publish_parser.add_argument("package")
    publish_parser.add_argument("--yes", action="store_true")
    publish_parser.set_defaults(func=command_publish)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
