from app import create_app
from app.models import WorldLocation
from app.services.world_map_service import WorldMapService


PROJECT_ID = 1
SOURCE_NOTE = "date course location batch"


def main():
    app = create_app()
    with app.app_context():
        service = WorldMapService()
        locations = (
            WorldLocation.query.filter(
                WorldLocation.project_id == PROJECT_ID,
                WorldLocation.source_note == SOURCE_NOTE,
                WorldLocation.deleted_at.is_(None),
            )
            .order_by(WorldLocation.sort_order.asc(), WorldLocation.id.asc())
            .all()
        )
        total_services = 0
        failed = []
        for index, location in enumerate(locations, start=1):
            try:
                synced = service.sync_location_services(location)
                total_services += len(synced or [])
                print(f"[{index}/{len(locations)}] {location.id} {location.name}: services={len(synced or [])}")
            except Exception as exc:
                failed.append((location.id, location.name, str(exc)))
                print(f"[{index}/{len(locations)}] {location.id} {location.name}: ERROR {exc}")
        print(f"locations={len(locations)} services={total_services} failed={len(failed)}")
        for location_id, name, error in failed:
            print(f"FAILED {location_id} {name}: {error}")


if __name__ == "__main__":
    main()
