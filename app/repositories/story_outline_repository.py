from ..extensions import db
from ..models.story_outline import StoryOutline


class StoryOutlineRepository:
    MUTABLE_FIELDS: tuple[str, ...] = (
        "premise",
        "protagonist_position",
        "main_goal",
        "branching_policy",
        "ending_policy",
        "outline_text",
        "outline_json",
    )
    def get_by_project(self, project_id: int):
        return StoryOutline.query.filter(StoryOutline.project_id == project_id).first()

    def upsert(self, project_id: int, payload: dict):
        outline = self.get_by_project(project_id)
        if outline:
            for field in self.MUTABLE_FIELDS:
                if field in payload:
                    setattr(outline, field, payload[field])
        else:
            data = {field: payload.get(field) for field in self.MUTABLE_FIELDS}
            outline = StoryOutline(project_id=project_id, **data)
            db.session.add(outline)
        db.session.commit()
        return outline
