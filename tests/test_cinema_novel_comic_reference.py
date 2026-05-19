from pathlib import Path

from app.extensions import db
from app.models import Asset, Character, CinemaNovel, CinemaNovelChapter, Project, User
from app.services.cinema_novel_service import CinemaNovelService
from app.utils import json_util


def _seed_comic_reference_case(tmp_path):
    user = User(email="comic-ref@example.com", display_name="Comic Ref", password_hash="x", role="project_user")
    db.session.add(user)
    db.session.flush()
    project = Project(owner_user_id=user.id, title="Laplace", genre="sf", project_type="linear")
    db.session.add(project)
    db.session.flush()

    asset_dir = Path(tmp_path)
    noa_path = asset_dir / "noa.png"
    shion_path = asset_dir / "shion.png"
    noa_path.write_bytes(b"noa")
    shion_path.write_bytes(b"shion")
    noa_asset = Asset(project_id=project.id, asset_type="reference_image", file_name="noa.png", file_path=str(noa_path))
    shion_asset = Asset(project_id=project.id, asset_type="reference_image", file_name="shion.png", file_path=str(shion_path))
    db.session.add_all([noa_asset, shion_asset])
    db.session.flush()

    noa = Character(
        project_id=project.id,
        name="\u30ce\u30a2",
        nickname="\u30ce\u30a2",
        base_asset_id=noa_asset.id,
        appearance_summary="\u9280\u9aea\u306e\u5973\u6027\u578b\u30d2\u30e5\u30fc\u30de\u30ce\u30a4\u30c9",
    )
    shion = Character(
        project_id=project.id,
        name="\u30b7\u30aa\u30f3",
        nickname="\u795e\u306e\u60aa\u622f",
        base_asset_id=shion_asset.id,
        appearance_summary="\u9ed2\u9aea\u306e\u5973\u6027\u3001\u9ed2\u767d\u306e\u4fee\u9053\u670d",
    )
    db.session.add_all([noa, shion])
    db.session.flush()

    novel = CinemaNovel(
        project_id=project.id,
        created_by_user_id=user.id,
        title="Comic",
        mode="short_comic",
        mobile_visible=True,
        production_json=json_util.dumps({"source_input": {"short_comic_art_style": "reference_image"}}),
    )
    db.session.add(novel)
    db.session.flush()
    scene = {
        "caption": "\u7948\u308a\u4e09\u5de5\u7a0b",
        "image_prompt": "\u30ea\u30f3\u30b0\u8107\u3001\u30b7\u30aa\u30f3\u304c\u767d\u30b0\u30ed\u30fc\u30d6\u3092\u5408\u308f\u305b\u308b",
        "character_ids": [noa.id],
        "characters": ["\u30ce\u30a2"],
    }
    chapter = CinemaNovelChapter(novel_id=novel.id, chapter_no=1, title="Chapter", scene_json=json_util.dumps([scene]))
    db.session.add(chapter)
    db.session.commit()
    return novel, chapter, noa, shion, noa_asset, shion_asset


def test_update_comic_scene_replaces_stale_character_ids_from_prompt(app, tmp_path):
    novel, chapter, noa, shion, _noa_asset, _shion_asset = _seed_comic_reference_case(tmp_path)
    service = CinemaNovelService()

    service.update_comic_scene(
        novel.id,
        {
            "chapter_id": chapter.id,
            "scene_index": 0,
            "image_prompt": "\u30ea\u30f3\u30b0\u8107\u3001\u30b7\u30aa\u30f3\u304c\u767d\u30b0\u30ed\u30fc\u30d6\u3092\u5408\u308f\u305b\u308b",
        },
    )

    refreshed = db.session.get(CinemaNovelChapter, chapter.id)
    scene = json_util.loads(refreshed.scene_json)[0]
    assert scene["character_ids"] == [shion.id]
    assert scene["characters"] == ["\u30b7\u30aa\u30f3"]


def test_generate_comic_panel_prefers_prompt_character_over_stale_scene_id(app, tmp_path):
    novel, _chapter, _noa, _shion, _noa_asset, shion_asset = _seed_comic_reference_case(tmp_path)
    service = CinemaNovelService()
    captured_jobs = []

    def fake_generate_jobs(jobs, **_kwargs):
        captured_jobs.extend(jobs)
        for job in jobs:
            yield job, None, "skip generation"

    service._generate_cinema_asset_jobs = fake_generate_jobs

    service.generate_short_comic_panel_images(novel.id, {"overwrite": True, "parallel": False})

    assert captured_jobs
    assert captured_jobs[0]["reference_asset_ids"] == [shion_asset.id]
    assert "Characters in this panel: \u30b7\u30aa\u30f3" in captured_jobs[0]["prompt"]
    assert "Add this exact Japanese headline text inside the image" in captured_jobs[0]["prompt"]
    assert "\u7948\u308a\u4e09\u5de5\u7a0b" in captured_jobs[0]["prompt"]
    assert "Do not render the headline text" not in captured_jobs[0]["prompt"]
    assert "Do not replace a registered character with a generic boxer" in captured_jobs[0]["prompt"]
    assert "\u9ed2\u9aea\u306e\u5973\u6027" in captured_jobs[0]["prompt"]


def test_matching_character_references_ignores_negated_character_names(app, tmp_path):
    _novel, _chapter, _noa, shion, _noa_asset, _shion_asset = _seed_comic_reference_case(tmp_path)
    service = CinemaNovelService()

    refs = service._matching_character_references(
        shion.project_id,
        "\u30b7\u30aa\u30f3\u304c\u7948\u308b\u3002\u30ce\u30a2\u51fa\u3055\u306a\u3044\u3002",
        limit=3,
    )

    assert [item["id"] for item in refs] == [shion.id]
