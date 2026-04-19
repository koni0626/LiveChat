import os
import mimetypes
from typing import Any, Optional

import requests


class ImageAIClient:
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

    def _build_request_payload(
        self,
        prompt: str,
        *,
        negative_prompt: Optional[str] = None,
        size: Optional[str] = None,
        style: Optional[str] = None,
        seed: Optional[int] = None,
        model: Optional[str] = None,
        response_format: str = "b64_json",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._resolve_model(model),
            "prompt": self._normalize_prompt(prompt),
            "size": size or "1024x1024",
            "response_format": response_format,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if style:
            payload["style"] = style
        if seed is not None:
            payload["seed"] = seed
        return payload

    def _build_edit_request_data(
        self,
        prompt: str,
        *,
        size: Optional[str] = None,
        style: Optional[str] = None,
        seed: Optional[int] = None,
        model: Optional[str] = None,
        response_format: str = "b64_json",
        input_fidelity: Optional[str] = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "model": self._resolve_model(model),
            "prompt": self._normalize_prompt(prompt),
            "size": size or "1024x1024",
            "response_format": response_format,
        }
        if style:
            data["style"] = style
        if seed is not None:
            data["seed"] = str(seed)
        if input_fidelity:
            data["input_fidelity"] = input_fidelity
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

            response = requests.post(
                "https://api.openai.com/v1/images/edits",
                headers={"Authorization": f"Bearer {self._get_api_key()}"},
                data=data,
                files=files,
                timeout=self._resolve_timeout(),
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise RuntimeError("image edit request timed out") from exc
        except FileNotFoundError as exc:
            raise RuntimeError("reference image file was not found") from exc
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
        style: Optional[str] = None,
        seed: Optional[int] = None,
        model: Optional[str] = None,
        response_format: str = "b64_json",
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
                style=style,
                seed=seed,
                model=resolved_model,
                response_format=response_format,
                input_fidelity=input_fidelity,
            )
            response_json = self._call_openai_image_edits_api(data, normalized_input_paths)
            result = self._normalize_response(
                response_json, prompt=normalized_prompt, model=resolved_model, response_format=response_format
            )
            result["operation"] = "edit"
            result["reference_image_count"] = len(normalized_input_paths)
            result["input_fidelity"] = input_fidelity or "low"
            return result

        payload = self._build_request_payload(
            normalized_prompt,
            negative_prompt=negative_prompt,
            size=size,
            style=style,
            seed=seed,
            model=resolved_model,
            response_format=response_format,
        )
        response_json = self._call_openai_images_api(payload)
        result = self._normalize_response(
            response_json, prompt=normalized_prompt, model=resolved_model, response_format=response_format
        )
        result["operation"] = "generate"
        result["reference_image_count"] = 0
        result["input_fidelity"] = None
        return result
