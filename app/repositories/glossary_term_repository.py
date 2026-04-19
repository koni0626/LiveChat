from ..extensions import db
from ..models import GlossaryTerm, World


class GlossaryTermRepository:
    def _base_query(self):
        return GlossaryTerm.query.join(World, GlossaryTerm.world_id == World.id)

    def list_by_project(self, project_id: int, category: str | None = None, search: str | None = None):
        query = self._base_query().filter(World.project_id == project_id)
        if category:
            query = query.filter(GlossaryTerm.category == category)
        if search:
            keyword = f"%{search.strip()}%"
            query = query.filter(
                db.or_(
                    GlossaryTerm.term.ilike(keyword),
                    GlossaryTerm.reading.ilike(keyword),
                    GlossaryTerm.description.ilike(keyword),
                )
            )
        return query.order_by(GlossaryTerm.sort_order.asc(), GlossaryTerm.id.asc()).all()

    def list_by_world(self, world_id: int, category: str | None = None):
        query = GlossaryTerm.query.filter(GlossaryTerm.world_id == world_id)
        if category:
            query = query.filter(GlossaryTerm.category == category)
        return query.order_by(GlossaryTerm.sort_order.asc(), GlossaryTerm.id.asc()).all()

    def get(self, term_id: int, project_id: int | None = None):
        query = GlossaryTerm.query
        if project_id is not None:
            query = self._base_query().filter(World.project_id == project_id)
        return query.filter(GlossaryTerm.id == term_id).first()

    def _resolve_world_id(self, project_id: int | None, world_id: int | None):
        if project_id is not None:
            world = World.query.filter(World.project_id == project_id).first()
            return world.id if world else None
        return world_id

    def create(self, project_id: int | None, payload: dict):
        world_id = self._resolve_world_id(project_id, payload.get("world_id"))
        if not world_id:
            return None
        term = GlossaryTerm(
            world_id=world_id,
            term=payload["term"],
            reading=payload.get("reading"),
            description=payload.get("description"),
            category=payload.get("category"),
            sort_order=payload.get("sort_order", 0),
        )
        db.session.add(term)
        db.session.commit()
        return term

    def update(self, term_id: int, payload: dict, project_id: int | None = None):
        term = self.get(term_id, project_id=project_id)
        if not term:
            return None

        world_id = self._resolve_world_id(project_id, payload.get("world_id"))
        if world_id:
            term.world_id = world_id

        for field in ("term", "reading", "description", "category", "sort_order"):
            if field in payload:
                setattr(term, field, payload[field])

        db.session.commit()
        return term

    def delete(self, term_id: int, project_id: int | None = None):
        term = self.get(term_id, project_id=project_id)
        if not term:
            return False
        db.session.delete(term)
        db.session.commit()
        return True
