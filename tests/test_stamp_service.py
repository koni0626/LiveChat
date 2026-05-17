import base64
from io import BytesIO

from PIL import Image

from app.extensions import db
from app.models import User
from app.models.asset import Asset
from app.models.character import Character
from app.models.project import Project
from app.services.stamp_service import StampService
from app.utils import json_util


def _png_base64(color=(120, 90, 200)):
    buffer = BytesIO()
    Image.new("RGB", (64, 64), color).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class _FakeImageAI:
    def __init__(self):
        self.calls = []

    def generate_image(self, prompt, **kwargs):
        self.calls.append({"prompt": prompt, **kwargs})
        return {"image_base64": _png_base64(), "revised_prompt": "revised"}


def _create_character_with_base_image(app, tmp_path):
    app.config["STORAGE_ROOT"] = str(tmp_path)
    base_dir = tmp_path / "projects" / "1" / "assets" / "reference_image"
    base_dir.mkdir(parents=True)
    base_path = base_dir / "noah_base.png"
    base_path.write_bytes(base64.b64decode(_png_base64(color=(20, 20, 40))))

    user = User(email="stamp@example.com", display_name="Stamp User", password_hash="x", role="project_user")
    db.session.add(user)
    db.session.flush()
    project = Project(owner_user_id=user.id, title="Laplace", genre="fantasy", project_type="linear")
    db.session.add(project)
    db.session.flush()
    base_asset = Asset(
        project_id=project.id,
        asset_type="reference_image",
        file_name="noah_base.png",
        file_path=str(base_path),
        mime_type="image/png",
        file_size=base_path.stat().st_size,
        width=64,
        height=64,
    )
    db.session.add(base_asset)
    db.session.flush()
    character = Character(
        project_id=project.id,
        name="ノア",
        nickname="ノア",
        base_asset_id=base_asset.id,
        appearance_summary="短い茶髪、青い発光アクセサリ、淡い星空のワンピース。",
        personality="やわらかい雰囲気。",
    )
    db.session.add(character)
    db.session.commit()
    return project, character, base_asset


def test_generate_stamp_uses_character_base_image_and_saves_asset(app, tmp_path):
    project, character, base_asset = _create_character_with_base_image(app, tmp_path)
    image_ai = _FakeImageAI()
    service = StampService(image_ai_client=image_ai)

    stamp = service.generate_stamp(
        project.id,
        {
            "character_id": character.id,
            "text": "可愛いっ！",
            "quality": "low",
            "size": "1024x1024",
            "model": "gpt-image-2",
            "provider": "openai",
        },
    )

    assert stamp["asset_type"] == "character_stamp"
    assert stamp["character_id"] == character.id
    assert stamp["character_name"] == "ノア"
    assert stamp["text"] == "可愛いっ！"
    assert stamp["media_url"].endswith(stamp["file_name"])
    assert image_ai.calls[0]["input_image_paths"] == [base_asset.file_path]
    assert 'exactly "可愛いっ！"' in image_ai.calls[0]["prompt"]

    asset = Asset.query.get(stamp["asset_id"])
    metadata = json_util.loads(asset.metadata_json)
    assert metadata["source"] == "stamp_generator"
    assert metadata["base_asset_id"] == base_asset.id
    assert asset.asset_type == "character_stamp"
    assert asset.width == 64
    assert asset.height == 64


def test_generate_stamp_requires_base_image(app, tmp_path):
    app.config["STORAGE_ROOT"] = str(tmp_path)
    user = User(email="stamp2@example.com", display_name="Stamp User", password_hash="x")
    db.session.add(user)
    db.session.flush()
    project = Project(owner_user_id=user.id, title="Laplace", genre="fantasy", project_type="linear")
    db.session.add(project)
    db.session.flush()
    character = Character(project_id=project.id, name="ノア")
    db.session.add(character)
    db.session.commit()

    service = StampService(image_ai_client=_FakeImageAI())

    try:
        service.generate_stamp(project.id, {"character_id": character.id, "text": "おはよう"})
    except ValueError as exc:
        assert "base image" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_stamps_page_and_list_endpoint(client, app, tmp_path):
    project, character, _base_asset = _create_character_with_base_image(app, tmp_path)
    stamp_path = tmp_path / "projects" / str(project.id) / "assets" / "character_stamp" / "stamp.png"
    stamp_path.parent.mkdir(parents=True, exist_ok=True)
    stamp_path.write_bytes(base64.b64decode(_png_base64()))
    stamp_asset = Asset(
        project_id=project.id,
        asset_type="character_stamp",
        file_name="stamp.png",
        file_path=str(stamp_path),
        mime_type="image/png",
        file_size=stamp_path.stat().st_size,
        width=64,
        height=64,
        metadata_json=json_util.dumps({"character_id": character.id, "character_name": "ノア", "text": "いいね"}),
    )
    db.session.add(stamp_asset)
    db.session.commit()
    with client.session_transaction() as flask_session:
        flask_session["user_id"] = project.owner_user_id

    page = client.get(f"/projects/{project.id}/stamps")
    assert page.status_code == 200
    assert "スタンプ".encode("utf-8") in page.data

    response = client.get(f"/api/v1/projects/{project.id}/stamps")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data[0]["text"] == "いいね"
    assert data[0]["media_url"].endswith("/projects/1/assets/character_stamp/stamp.png")
