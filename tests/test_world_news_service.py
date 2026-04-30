from types import SimpleNamespace

from app.services.world_news_service import WorldNewsService


class _Repo:
    def __init__(self, existing):
        self.existing = existing

    def find_by_source(self, **_kwargs):
        return self.existing


class _Characters:
    def get(self, _character_id):
        return None


class _Locations:
    def get(self, _location_id):
        return None


class _Assets:
    def get_asset(self, _asset_id):
        return None


def test_outing_completion_existing_news_generates_missing_image(monkeypatch):
    existing = SimpleNamespace(
        id=7,
        project_id=1,
        created_by_user_id=2,
        related_character_id=3,
        related_location_id=4,
        news_type="outing_afterglow",
        title="after outing",
        body="body",
        summary=None,
        image_asset_id=None,
        importance=3,
        source_type="outing_completed",
        source_ref_type="outing",
        source_ref_id=9,
        return_url="/projects/1/outings",
        status="published",
        metadata_json=None,
        created_at=None,
        updated_at=None,
    )
    service = WorldNewsService(
        repository=_Repo(existing),
        character_repository=_Characters(),
        location_repository=_Locations(),
        asset_service=_Assets(),
    )

    called = {"ensure": False}

    def ensure_news_image(item):
        called["ensure"] = True
        item.image_asset_id = 99
        return item

    monkeypatch.setattr(service, "_ensure_news_image", ensure_news_image)
    outing = SimpleNamespace(project_id=1, id=9)

    result = service.create_for_outing_completed(outing, None, None, {})

    assert called["ensure"] is True
    assert result["image_asset_id"] == 99


def test_ensure_news_image_records_empty_response_metadata(monkeypatch):
    item = SimpleNamespace(
        id=8,
        image_asset_id=None,
        metadata_json=None,
    )
    service = WorldNewsService()

    monkeypatch.setattr(
        service,
        "_generate_news_image",
        lambda _item: (
            None,
            {
                "provider": "openai",
                "model": "gpt-image-2",
                "reference_asset_ids": [1, 2],
            },
        ),
    )

    committed = {"value": False}

    class _Session:
        def commit(self):
            committed["value"] = True

    import app.extensions

    monkeypatch.setattr(app.extensions.db, "session", _Session())

    service._ensure_news_image(item)

    assert committed["value"] is True
    assert item.image_asset_id is None
    assert "empty_response" in item.metadata_json
    assert "gpt-image-2" in item.metadata_json
