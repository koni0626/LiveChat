from app import create_app
from app.extensions import db
from app.models import WorldLocation


PROJECT_ID = 1


app = create_app()
with app.app_context():
    rows = (
        WorldLocation.query.filter(
            WorldLocation.project_id == PROJECT_ID,
            WorldLocation.source_note == "date course location batch",
            WorldLocation.deleted_at.is_(None),
        )
        .order_by(WorldLocation.id.asc())
        .all()
    )
    for index, row in enumerate(rows):
        row.sort_order = -10000 + index
        db.session.add(row)
    db.session.commit()
    print(f"prioritized={len(rows)}")
