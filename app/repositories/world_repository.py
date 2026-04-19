from ..extensions import db
from ..models.world import World


class WorldRepository:
    MUTABLE_FIELDS: tuple[str, ...] = (
        "name",
        "era_description",
        "technology_level",
        "social_structure",
        "tone",
        "overview",
        "rules_json",
        "forbidden_json",
    )

    def get_by_project(self, project_id: int):
        return World.query.filter_by(project_id=project_id).first()

    def upsert(self, project_id: int, payload: dict):
        world = self.get_by_project(project_id)
        if world is None:
            data = {field: payload.get(field) for field in self.MUTABLE_FIELDS}
            world = World(project_id=project_id, **data)
            db.session.add(world)
        else:
            for field in self.MUTABLE_FIELDS:
                if field in payload:
                    setattr(world, field, payload[field])
        db.session.commit()
        return world
