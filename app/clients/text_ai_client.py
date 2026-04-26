import json
import os
import base64
import mimetypes
from typing import Any, Optional

import requests


class TextAIClient:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, provider: str = "openai") -> None:
        self._api_key = api_key
        self._model = model
        self._provider = provider

    def _get_api_key(self) -> str:
        api_key = self._api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        return api_key

    def _resolve_model(self, model: Optional[str] = None) -> str:
        return model or self._model or os.getenv("TEXT_AI_MODEL") or "gpt-5.4-mini"

    def _resolve_vision_model(self, model: Optional[str] = None) -> str:
        return model or os.getenv("TEXT_AI_VISION_MODEL") or os.getenv("TEXT_AI_MODEL") or "gpt-4.1-mini"

    def _max_tokens_parameter_name(self, model: str) -> str:
        normalized = (model or "").lower()
        if normalized.startswith("gpt-5"):
            return "max_completion_tokens"
        return "max_tokens"

    def _resolve_timeout(self) -> int:
        return int(os.getenv("TEXT_AI_TIMEOUT_SECONDS", "120"))

    def _normalize_prompt(self, prompt: str) -> str:
        value = str(prompt or "").strip()
        if not value:
            raise ValueError("prompt is required")
        return value

    def _build_messages(self, prompt: str, system_prompt: Optional[str] = None) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _build_image_data_url(self, file_path: str) -> str:
        with open(file_path, "rb") as file_handle:
            encoded = base64.b64encode(file_handle.read()).decode("ascii")
        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        return f"data:{mime_type};base64,{encoded}"

    def _call_openai_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._get_api_key()}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._resolve_timeout(),
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise RuntimeError("text generation request timed out") from exc
        except requests.RequestException as exc:
            raise RuntimeError("text generation request failed") from exc

    def _extract_text(self, response_json: dict[str, Any]) -> str:
        choices = response_json.get("choices") or []
        if not choices:
            raise RuntimeError("text generation response is invalid")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("text generation response is invalid")
        return content.strip()

    def _extract_usage(self, response_json: dict[str, Any]) -> Optional[dict[str, Any]]:
        usage = response_json.get("usage")
        if not usage:
            return None
        return {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }

    def _try_parse_json(self, text: str):
        try:
            return json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    def generate_text(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        response_format: Optional[dict[str, Any]] = None,
        max_tokens: Optional[int] = None,
    ) -> dict[str, Any]:
        normalized_prompt = self._normalize_prompt(prompt)
        resolved_model = self._resolve_vision_model(model)
        payload: dict[str, Any] = {"model": resolved_model, "messages": self._build_messages(normalized_prompt, system_prompt)}
        if temperature is not None:
            payload["temperature"] = temperature
        if response_format is not None:
            payload["response_format"] = response_format
        if max_tokens is not None:
            payload[self._max_tokens_parameter_name(resolved_model)] = max_tokens

        response_json = self._call_openai_chat(payload)
        text = self._extract_text(response_json)
        return {
            "provider": self._provider,
            "model": resolved_model,
            "text": text,
            "usage": self._extract_usage(response_json),
            "raw_response": response_json,
        }

    def generate_scene(self, prompt: str, *, model: Optional[str] = None) -> dict[str, Any]:
        return self.generate_text(prompt, model=model, temperature=0.9)

    def extract_state_json(self, prompt: str, *, model: Optional[str] = None) -> dict[str, Any]:
        result = self.generate_text(
            prompt,
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        result["parsed_json"] = self._try_parse_json(result["text"])
        return result

    def analyze_image(
        self,
        file_path: str,
        *,
        prompt: Optional[str] = None,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        if not file_path or not os.path.exists(file_path):
            raise ValueError("file_path is required")
        resolved_model = self._resolve_vision_model(model)
        user_prompt = self._normalize_prompt(
            prompt
            or (
                "Return only JSON. "
                "Describe the main object in the image for a gift scene. "
                'Required keys: label, short_description, tags, likely_categories. '
                "tags and likely_categories must be arrays of short strings."
            )
        )
        content = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": self._build_image_data_url(file_path)}},
        ]
        payload: dict[str, Any] = {
            "model": resolved_model,
            "messages": ([{"role": "system", "content": system_prompt}] if system_prompt else []) + [
                {"role": "user", "content": content}
            ],
            "response_format": {"type": "json_object"},
        }
        response_json = self._call_openai_chat(payload)
        text = self._extract_text(response_json)
        return {
            "provider": self._provider,
            "model": resolved_model,
            "text": text,
            "parsed_json": self._try_parse_json(text),
            "usage": self._extract_usage(response_json),
            "raw_response": response_json,
        }
