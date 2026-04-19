from ..extensions import db
from ..models.usage_log import UsageLog


class UsageLogRepository:
    ALLOWED_FIELDS = {
        "user_id",
        "project_id",
        "action_type",
        "quantity",
        "unit",
        "detail_json",
    }
    def create(self, payload: dict):
        data = {key: payload[key] for key in self.ALLOWED_FIELDS if key in payload}
        log = UsageLog(**data)
        db.session.add(log)
        db.session.commit()
        return log
