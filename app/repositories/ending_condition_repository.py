from ..extensions import db
from ..models.ending_condition import EndingCondition


class EndingConditionRepository:
    def list_by_project(self, project_id: int):
        return (
            EndingCondition.query.filter_by(project_id=project_id)
            .order_by(EndingCondition.priority, EndingCondition.id)
            .all()
        )

    def get(self, ending_condition_id: int):
        return EndingCondition.query.get(ending_condition_id)

    def create(self, project_id: int, payload: dict):
        ending_condition = EndingCondition(
            project_id=project_id,
            ending_type=payload["ending_type"],
            name=payload["name"],
            condition_text=payload.get("condition_text"),
            condition_json=payload.get("condition_json"),
            priority=payload.get("priority", 0),
        )
        db.session.add(ending_condition)
        db.session.commit()
        return ending_condition

    def update(self, ending_condition_id: int, payload: dict):
        ending_condition = self.get(ending_condition_id)
        if not ending_condition:
            return None
        for field in (
            "ending_type",
            "name",
            "condition_text",
            "condition_json",
            "priority",
        ):
            if field in payload:
                setattr(ending_condition, field, payload[field])
        db.session.commit()
        return ending_condition

    def delete(self, ending_condition_id: int):
        ending_condition = self.get(ending_condition_id)
        if not ending_condition:
            return False
        db.session.delete(ending_condition)
        db.session.commit()
        return True
