from ..repositories.usage_log_repository import UsageLogRepository
from ..utils import json_util


class UsageLogService:
    ALLOWED_FIELDS = {
        'user_id',
        'project_id',
        'action_type',
        'quantity',
        'unit',
        'detail_json',
    }

    def __init__(self, repository: UsageLogRepository | None = None):
        self._repo = repository or UsageLogRepository()

    def _ensure_payload(self, payload: dict | None) -> dict:
        if not isinstance(payload, dict):
            raise ValueError('payload must be a dict')
        return payload

    def _ensure_int(self, value, field_name: str, *, allow_none: bool = False, minimum: int | None = None):
        if value is None:
            if allow_none:
                return None
            raise ValueError(f'{field_name} is required')
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f'{field_name} must be an integer')
        if minimum is not None and value < minimum:
            raise ValueError(f'{field_name} must be >= {minimum}')
        return value

    def _normalize_detail_json(self, value):
        if value is None or isinstance(value, str):
            return value
        if isinstance(value, (dict, list)):
            return json_util.dumps(value)
        raise ValueError('detail_json must be a string, dict, list, or None')

    def _normalize_payload(self, payload: dict) -> dict:
        payload = self._ensure_payload(payload)
        unknown = set(payload.keys()) - self.ALLOWED_FIELDS
        if unknown:
            raise ValueError('unsupported fields: ' + ', '.join(sorted(unknown)))

        normalized: dict[str, object] = {}
        normalized['user_id'] = self._ensure_int(payload.get('user_id'), 'user_id', minimum=1)

        if 'project_id' in payload:
            normalized['project_id'] = self._ensure_int(
                payload.get('project_id'),
                'project_id',
                allow_none=True,
                minimum=1,
            )

        action_type = payload.get('action_type')
        if action_type is None:
            raise ValueError('action_type is required')
        action_type = str(action_type).strip()
        if not action_type:
            raise ValueError('action_type is required')
        normalized['action_type'] = action_type

        quantity = payload.get('quantity', 1)
        normalized['quantity'] = self._ensure_int(quantity, 'quantity', minimum=1)

        if 'unit' in payload:
            unit = payload.get('unit')
            normalized['unit'] = None if unit is None else str(unit).strip()

        if 'detail_json' in payload:
            normalized['detail_json'] = self._normalize_detail_json(payload.get('detail_json'))

        return normalized
    def create_log(self, payload: dict):
        normalized = self._normalize_payload(payload)
        return self._repo.create(normalized)
