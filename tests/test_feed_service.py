from types import SimpleNamespace

import pytest

from app.services.feed_service import FeedService
from app.services.user_setting_service import UserSettingService


class _Repo:
    def __init__(self):
        self.created = []

    def create_post(self, payload):
        post = SimpleNamespace(id=len(self.created) + 1, **payload)
        self.created.append(post)
        return post

    def list_posts(self, **_kwargs):
        return []


class _Characters:
    def __init__(self, character):
        self.character = character

    def get_character(self, character_id):
        return self.character if character_id == self.character.id else None

    def list_characters(self, project_id):
        return [self.character] if self.character.project_id == project_id else []


class _Locations:
    def __init__(self, locations=None):
        self.locations = locations or []

    def list_by_project(self, project_id):
        return [location for location in self.locations if location.project_id == project_id]


class _Outfits:
    def __init__(self, outfits=None):
        self.outfits = outfits or []

    def list_by_character(self, character_id):
        return [outfit for outfit in self.outfits if outfit.character_id == character_id]


def test_generate_posts_creates_published_post_and_generates_image(monkeypatch):
    character = SimpleNamespace(id=3, project_id=1, name="Noa")
    repo = _Repo()
    service = FeedService(repository=repo, character_service=_Characters(character))

    monkeypatch.setattr(
        service,
        "_generate_feed_candidates",
        lambda project_id, count, **_kwargs: [{"character_id": character.id, "body": "今日は少しだけ特別な空気でした。"}],
    )
    monkeypatch.setattr(service, "refresh_character_feed_profile", lambda _character_id: None)
    generated = {"called": False}

    def generate_post_image(post_id, payload):
        generated["called"] = True
        post = repo.created[post_id - 1]
        post.image_asset_id = 42
        return post

    monkeypatch.setattr(service, "generate_post_image", generate_post_image)

    posts = service.generate_posts(project_id=1, user_id=2, payload={"count": 1})

    assert len(posts) == 1
    assert repo.created[0].status == "published"
    assert repo.created[0].image_asset_id == 42
    assert generated["called"] is True


def test_solo_feed_candidate_rejects_other_project_character_name():
    target = SimpleNamespace(id=1, name="ノア", nickname=None)
    other = SimpleNamespace(id=2, name="レイナ", nickname=None)
    service = FeedService()

    with pytest.raises(RuntimeError):
        service._normalize_feed_candidate_characters(
            [{"character_id": 1, "body": "ゲーム筐体の前でレイナがスコア表示を見て固まった。"}],
            [target],
            post_plans=[{"character_id": 1, "post_pattern": "test"}],
            all_characters=[target, other],
        )


def test_photobook_mode_creates_thin_caption_without_generating_image(monkeypatch):
    character = SimpleNamespace(id=3, project_id=1, name="導巫女さん", nickname="ブラック企業")
    location = SimpleNamespace(
        id=7,
        project_id=1,
        name="星灯り神社",
        region="北区",
        location_type="shrine",
        tags_json='["夜景", "桜"]',
        description="星灯りがきれいに見える高台の神社。",
        image_prompt="a hilltop shrine with starlight and soft lanterns",
        status="published",
    )
    outfit = SimpleNamespace(
        id=9,
        project_id=1,
        character_id=3,
        name="白緋の導き衣装",
        description="白い布と赤い紐飾りの衣装。",
        asset_id=44,
        usage_scene="photobook",
        season="all",
        mood="clean",
        color_notes="white and red",
        fixed_parts="red cords",
        allowed_changes="pose and lighting only",
        ng_rules=None,
        prompt_notes="keep the shrine maiden silhouette",
        is_default=True,
        status="active",
    )
    repo = _Repo()
    service = FeedService(
        repository=repo,
        character_service=_Characters(character),
        location_repository=_Locations([location]),
        outfit_repository=_Outfits([outfit]),
    )

    monkeypatch.setattr(service, "refresh_character_feed_profile", lambda _character_id: None)
    generated = {"called": False}

    def generate_post_image(post_id, payload):
        generated["called"] = True
        post = repo.created[post_id - 1]
        post.image_asset_id = 42
        return post

    monkeypatch.setattr(service, "generate_post_image", generate_post_image)

    posts = service.generate_posts(
        project_id=1,
        user_id=2,
        payload={"count": 1, "interaction_mode": "photobook", "character_id": character.id},
    )

    assert len(posts) == 1
    assert repo.created[0].status == "published"
    assert not hasattr(repo.created[0], "image_asset_id")
    assert repo.created[0].body.endswith("\n\n#AIイラスト #AIArt")
    assert "導巫女" in repo.created[0].body
    assert "導巫女さん" not in repo.created[0].body
    assert "ブラック企業" not in repo.created[0].body
    assert "星灯り神社" not in repo.created[0].body
    state = service._load_json(repo.created[0].generation_state_json)
    scene_anchor = state["candidate"]["scene_anchor"]
    assert scene_anchor["location_name"] == "星灯り神社"
    assert scene_anchor["outfit_source"] == "closet"
    assert scene_anchor["outfit_id"] == 9
    assert scene_anchor["outfit_asset_id"] == 44
    assert "白緋の導き衣装" in scene_anchor["outfit_prompt"]
    assert generated["called"] is False


def test_image_settings_do_not_keep_text_model_as_image_model():
    service = UserSettingService()

    options = service._apply_image_generation_settings(
        {
            "image_ai_provider": "openai",
            "image_ai_model": "gpt-image-2",
            "default_quality": "medium",
            "default_size": "1024x1024",
            "mobile_default_size": "1024x1536",
            "prefer_portrait_on_mobile": False,
        },
        {"model": "gpt-5.4-mini"},
    )

    assert options["model"] == "gpt-image-2"
