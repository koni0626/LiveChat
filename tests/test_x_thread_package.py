import json

import pytest

from scripts.x_thread_package import _looks_like_mojibake_prompt, command_preview


class _Args:
    def __init__(self, package, out):
        self.package = str(package)
        self.out = str(out)


def test_preview_adds_default_hashtags_and_images(tmp_path):
    image_path = tmp_path / "thumb.png"
    image_path.write_bytes(b"not-a-real-image-for-preview")
    package_path = tmp_path / "thread.json"
    preview_path = tmp_path / "thread.preview.md"
    package_path.write_text(
        json.dumps(
            {
                "title": "第1話",
                "posts": [
                    {
                        "text": "人類は、プリンで滅びました。",
                        "image_path": str(image_path),
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    command_preview(_Args(package_path, preview_path))

    markdown = preview_path.read_text(encoding="utf-8")
    assert "# X Thread Preview: 第1話" in markdown
    assert "人類は、プリンで滅びました。" in markdown
    assert "#ラプラスシティ #小説" in markdown
    assert image_path.as_posix() in markdown.replace("\\", "/")


def test_preview_suggests_blog_hashtags(tmp_path):
    package_path = tmp_path / "thread.json"
    preview_path = tmp_path / "thread.preview.md"
    package_path.write_text(
        json.dumps(
            {
                "title": "静かな解雇",
                "character": "ノア",
                "hashtags": "auto",
                "posts": [{"text": "静かな解雇について、ノアはそう思います。AIと働き方の話です。"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    command_preview(_Args(package_path, preview_path))

    markdown = preview_path.read_text(encoding="utf-8")
    assert "#ラプラスシティ #ノアのブログ #AI #働き方" in markdown


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        ("プリンを奪う者に、未来を語る資格はない", False),
        ("???????????????????????????????????????????????", True),
        ("16:9 ???X?????????????????????????????????????????????", True),
    ],
)
def test_detects_mojibake_image_prompt(prompt, expected):
    assert _looks_like_mojibake_prompt(prompt) is expected
