import json


def dumps(data, **kwargs):
    return json.dumps(data, ensure_ascii=False, **kwargs)


def loads(payload: str):
    return json.loads(payload)
