import requests

from app.clients.text_ai_client import TextAIClient


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self._payload


def test_openai_chat_retries_http_500(monkeypatch):
    client = TextAIClient(api_key="test-key")
    responses = [
        _Response(500, {"error": {"message": "temporary failure"}}),
        _Response(200, {"choices": [{"message": {"content": "ok"}}]}),
    ]
    calls = []

    def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return responses.pop(0)

    monkeypatch.setenv("TEXT_AI_RETRY_ATTEMPTS", "2")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    monkeypatch.setattr("requests.post", fake_post)

    result = client._call_openai_chat({"model": "gpt-5.4-mini", "messages": []})

    assert result["choices"][0]["message"]["content"] == "ok"
    assert len(calls) == 2
