from app import create_app
from app.extensions import db
from app.models import WorldLocation
from app.repositories.world_location_service_repository import WorldLocationServiceRepository
from app.services.world_map_service import WorldMapService


PROJECT_ID = 1


def expanded_description(location):
    base = str(location.description or "").strip()
    tags = ", ".join(WorldMapService()._tags_from_json(location.tags_json))
    addition = (
        f"{location.name}はデートコースとして使える施設で、施設内に複数の行き先、体験、会話フックがある。"
        f"地域は{location.region or 'ラプラスシティ'}、種別は{location.location_type or '施設'}。"
        f"タグは{tags or 'デート'}。"
        "プレイヤーとキャラクターが次にどこへ行くか選べるように、具体的な店、席、展示、体験、イベントを持つ。"
    )
    return "\n".join(part for part in [base, addition] if part)


def main():
    app = create_app()
    with app.app_context():
        world_map_service = WorldMapService()
        service_repo = WorldLocationServiceRepository()
        locations = (
            WorldLocation.query.filter(
                WorldLocation.project_id == PROJECT_ID,
                WorldLocation.id >= 34,
                WorldLocation.id <= 94,
                WorldLocation.deleted_at.is_(None),
            )
            .order_by(WorldLocation.sort_order.asc(), WorldLocation.id.asc())
            .all()
        )
        total_services = 0
        touched = 0
        failed = []
        for index, location in enumerate(locations, start=1):
            existing_services = service_repo.list_by_location(location.id)
            if existing_services:
                print(f"[{index}/{len(locations)}] {location.id} {location.name}: skip existing={len(existing_services)}")
                total_services += len(existing_services)
                continue
            if len(str(location.description or "").strip()) < 80:
                location.description = expanded_description(location)
                db.session.add(location)
                db.session.commit()
            try:
                synced = world_map_service.sync_location_services(location)
                total_services += len(synced or [])
                touched += 1
                print(f"[{index}/{len(locations)}] {location.id} {location.name}: services={len(synced or [])}")
            except Exception as exc:
                failed.append((location.id, location.name, str(exc)))
                print(f"[{index}/{len(locations)}] {location.id} {location.name}: ERROR {exc}")
        print(f"locations={len(locations)} synced_locations={touched} services_total_seen={total_services} failed={len(failed)}")
        for location_id, name, error in failed:
            print(f"FAILED {location_id} {name}: {error}")


if __name__ == "__main__":
    main()
