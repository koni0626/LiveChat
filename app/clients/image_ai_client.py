import mimetypes
import os
from typing import Any, Optional

import requests


class ImageAIClient:
    SUPPORTED_SIZES = {"auto", "512x512", "1024x1024", "1024x1536", "1536x1024"}
    SUPPORTED_QUALITIES = {"auto", "low", "medium", "high"}
    SUPPORTED_FORMATS = {"png", "jpeg", "webp"}
    SUPPORTED_BACKGROUNDS = {"auto", "opaque", "transparent"}
    SUPPORTED_INPUT_FIDELITY = {"low", "high"}
    SIZE_ALIASES = {
        "square_small": "512x512",
        "square_sm": "512x512",
        "square_preview": "512x512",
        "square_default": "1024x1024",
        "square_large": "1024x1024",
        "portrait": "1024x1536",
        "portrait_large": "1024x1536",
        "landscape": "1536x1024",
        "landscape_large": "1536x1024",
        "lowcost": "512x512",
        "low_cost": "512x512",
    }

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
        return model or self._model or os.getenv("IMAGE_AI_MODEL") or "gpt-image-1.5"

    def _resolve_timeout(self) -> int:
        return int(os.getenv("IMAGE_AI_TIMEOUT_SECONDS", "60"))

    def _normalize_prompt(self, prompt: str) -> str:
        value = str(prompt or "").strip()
        if not value:
            raise ValueError("prompt is required")
        return value

    def _normalize_choice(
        self,
        raw_value: Optional[str],
        *,
        allowed: set[str],
        default: str,
        aliases: Optional[dict[str, str]] = None,
    ) -> str:
        normalized = str(raw_value or "").strip().lower()
        lookup_key = normalized.replace("-", "_")
        if aliases:
            normalized = aliases.get(lookup_key, normalized)
        if not normalized:
            return default
        return normalized if normalized in allowed else default

    def _extract_error_message(self, response: requests.Response, fallback: str) -> str:
        status_code = getattr(response, "status_code", None)
        try:
            payload = response.json()
        except ValueError:
            payload = None

        error_message = None
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                error_message = error.get("message") or error.get("code")
            elif isinstance(error, str):
                error_message = error
            if not error_message:
                error_message = payload.get("message")

        if not error_message:
            error_message = (response.text or "").strip() or fallback

        if status_code:
            return f"{fallback} ({status_code}): {error_message}"
        return f"{fallback}: {error_message}"

    def _build_request_payload(
        self,
        prompt: str,
        *,
        negative_prompt: Optional[str] = None,
        size: Optional[str] = None,
        model: Optional[str] = None,
        quality: Optional[str] = None,
        output_format: Optional[str] = None,
        background: Optional[str] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._resolve_model(model),
            "prompt": self._normalize_prompt(prompt),
            "size": self._normalize_choice(
                size,
                allowed=self.SUPPORTED_SIZES,
                default="1024x1024",
                aliases=self.SIZE_ALIASES,
            ),
            "n": 1,
            "quality": self._normalize_choice(
                quality,
                allowed=self.SUPPORTED_QUALITIES,
                default="low",
            ),
            "output_format": self._normalize_choice(
                output_format,
                allowed=self.SUPPORTED_FORMATS,
                default="png",
            ),
            "background": self._normalize_choice(
                background,
                allowed=self.SUPPORTED_BACKGROUNDS,
                default="auto",
            ),
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return payload

    def _build_edit_request_data(
        self,
        prompt: str,
        *,
        size: Optional[str] = None,
        model: Optional[str] = None,
        quality: Optional[str] = None,
        output_format: Optional[str] = None,
        background: Optional[str] = None,
        input_fidelity: Optional[str] = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "model": self._resolve_model(model),
            "prompt": self._normalize_prompt(prompt),
            "size": self._normalize_choice(
                size,
                allowed=self.SUPPORTED_SIZES,
                default="1024x1024",
                aliases=self.SIZE_ALIASES,
            ),
            "n": "1",
            "quality": self._normalize_choice(
                quality,
                allowed=self.SUPPORTED_QUALITIES,
                default="low",
            ),
            "output_format": self._normalize_choice(
                output_format,
                allowed=self.SUPPORTED_FORMATS,
                default="png",
            ),
            "background": self._normalize_choice(
                background,
                allowed=self.SUPPORTED_BACKGROUNDS,
                default="auto",
            ),
        }
        if input_fidelity:
            data["input_fidelity"] = self._normalize_choice(
                input_fidelity,
                allowed=self.SUPPORTED_INPUT_FIDELITY,
                default="high",
            )
        return data

    def _call_openai_images_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(
                "https://api.openai.com/v1/images/generations",
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
            raise RuntimeError("image generation request timed out") from exc
        except requests.HTTPError as exc:
            response = exc.response
            raise RuntimeError(self._extract_error_message(response, "image generation request failed")) from exc
        except requests.RequestException as exc:
            raise RuntimeError("image generation request failed") from exc

    def _call_openai_image_edits_api(self, data: dict[str, Any], image_paths: list[str]) -> dict[str, Any]:
        file_handles = []
        try:
            files = []
            for image_path in image_paths:
                mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
                file_handle = open(image_path, "rb")
                file_handles.append(file_handle)
                files.append(("image[]", (os.path.basename(image_path), file_handle, mime_type)))

            def send_request(request_data: dict[str, Any]):
                response = requests.post(
                    "https://api.openai.com/v1/images/edits",
                    headers={"Authorization": f"Bearer {self._get_api_key()}"},
                    data=request_data,
                    files=files,
                    timeout=self._resolve_timeout(),
                )
                response.raise_for_status()
                return response.json()

            try:
                return send_request(data)
            except requests.HTTPError as exc:
                response = exc.response
                message = self._extract_error_message(response, "image edit request failed")
                if "Unknown parameter: 'input_fidelity'" in message and "input_fidelity" in data:
                    fallback_data = dict(data)
                    fallback_data.pop("input_fidelity", None)
                    try:
                        return send_request(fallback_data)
                    except requests.HTTPError as retry_exc:
                        retry_response = retry_exc.response
                        retry_message = self._extract_error_message(retry_response, "image edit request failed")
                        raise RuntimeError(retry_message) from retry_exc
                raise RuntimeError(message) from exc
        except requests.Timeout as exc:
            raise RuntimeError("image edit request timed out") from exc
        except FileNotFoundError as exc:
            raise RuntimeError("reference image file was not found") from exc
        except requests.HTTPError as exc:
            response = exc.response
            raise RuntimeError(self._extract_error_message(response, "image edit request failed")) from exc
        except requests.RequestException as exc:
            raise RuntimeError("image edit request failed") from exc
        finally:
            for file_handle in file_handles:
                file_handle.close()

    def _normalize_response(
        self,
        response_json: dict[str, Any],
        *,
        prompt: str,
        model: str,
        response_format: str,
    ) -> dict[str, Any]:
        data_list = response_json.get("data") or []
        first = data_list[0] if data_list else {}
        return {
            "provider": self._provider,
            "model": model,
            "prompt": prompt,
            "response_format": response_format,
            "image_base64": first.get("b64_json"),
            "image_url": first.get("url"),
            "revised_prompt": response_json.get("revised_prompt") or first.get("revised_prompt"),
            "raw_response": response_json,
        }

    def generate_image(
        self,
        prompt: str,
        *,
        negative_prompt: Optional[str] = None,
        size: Optional[str] = None,
        model: Optional[str] = None,
        quality: Optional[str] = None,
        output_format: str = "png",
        background: str = "auto",
        input_image_paths: Optional[list[str]] = None,
        input_fidelity: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized_prompt = self._normalize_prompt(prompt)
        resolved_model = self._resolve_model(model)
        normalized_input_paths = [path for path in (input_image_paths or []) if path]

        if normalized_input_paths:
            data = self._build_edit_request_data(
                normalized_prompt,
                size=size,
                model=resolved_model,
                quality=quality,
                output_format=output_format,
                background=background,
                input_fidelity=input_fidelity,
            )
            response_json = self._call_openai_image_edits_api(data, normalized_input_paths)
            result = self._normalize_response(
                response_json, prompt=normalized_prompt, model=resolved_model, response_format="b64_json"
            )
            result["operation"] = "edit"
            result["reference_image_count"] = len(normalized_input_paths)
            result["input_fidelity"] = input_fidelity or "low"
            result["quality"] = data.get("quality")
            result["output_format"] = data.get("output_format")
            result["background"] = data.get("background")
            return result

        payload = self._build_request_payload(
            normalized_prompt,
            negative_prompt=negative_prompt,
            size=size,
            model=resolved_model,
            quality=quality,
            output_format=output_format,
            background=background,
        )
        response_json = self._call_openai_images_api(payload)
        result = self._normalize_response(
            response_json, prompt=normalized_prompt, model=resolved_model, response_format="b64_json"
        )
        result["operation"] = "generate"
        result["reference_image_count"] = 0
        result["input_fidelity"] = None
        result["quality"] = payload.get("quality")
        result["output_format"] = payload.get("output_format")
        result["background"] = payload.get("background")
        return result
