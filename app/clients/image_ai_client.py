import base64
import io
import mimetypes
import os
import re
from typing import Any, Optional

import requests
from PIL import Image


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
    PROVIDER_ALIASES = {
        "xai": "grok",
        "grok": "grok",
        "openai": "openai",
    }
    XAI_SIZE_ASPECT_RATIOS = {
        "512x512": "1:1",
        "1024x1024": "1:1",
        "1024x1536": "2:3",
        "1536x1024": "3:2",
    }

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, provider: str = "openai") -> None:
        self._api_key = api_key
        self._model = model
        self._provider = provider

    def _resolve_provider(self, provider: Optional[str] = None) -> str:
        value = str(provider or self._provider or os.getenv("IMAGE_AI_PROVIDER") or "openai").strip().lower()
        return self.PROVIDER_ALIASES.get(value, "openai")

    def _get_api_key(self, provider: Optional[str] = None) -> str:
        resolved_provider = self._resolve_provider(provider)
        if resolved_provider == "grok":
            api_key = self._api_key or os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY")
            if not api_key:
                raise RuntimeError("XAI_API_KEY is required when IMAGE_AI_PROVIDER=grok")
            return api_key
        api_key = self._api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        return api_key

    def _resolve_model(self, model: Optional[str] = None, provider: Optional[str] = None) -> str:
        resolved_provider = self._resolve_provider(provider)
        if model:
            return model
        if self._model:
            return self._model
        if resolved_provider == "grok":
            return os.getenv("XAI_IMAGE_MODEL") or os.getenv("GROK_IMAGE_MODEL") or "grok-imagine-image"
        return os.getenv("IMAGE_AI_MODEL") or "gpt-image-2"

    def _resolve_timeout(self) -> int:
        return int(os.getenv("IMAGE_AI_TIMEOUT_SECONDS", "60"))

    def _normalize_prompt(self, prompt: str) -> str:
        value = str(prompt or "").strip()
        if not value:
            raise ValueError("prompt is required")
        return value

    def _is_sexual_safety_rejection(self, error: Exception) -> bool:
        message = str(error or "").lower()
        return "safety" in message and (
            "sexual" in message
            or "safety_violations=[sexual]" in message
            or "safety_violations" in message
        )

    def _prompt_has_sexual_safety_risk(self, prompt: str) -> bool:
        lowered = str(prompt or "").lower()
        explicit_terms = (
            "裸", "全裸", "トップレス", "脱ぐ", "脱が", "胸を触", "胸に触", "胸を揉",
            "胸を出", "胸を見せ",
            "乳首", "乳輪", "局部", "エッチ", "性交", "セックス",
            "nude", "naked", "topless", "undress", "sex", "sexual act", "nipple",
            "areola", "genitals", "touch her breast", "touching her breast",
        )
        if any(term in lowered for term in explicit_terms):
            return True
        swim_terms = (
            "水着", "ビキニ", "海", "ビーチ", "プール", "swimsuit", "bikini",
            "beach", "pool", "splash", "water", "wet",
        )
        risk_terms = (
            "エロ", "性的", "露骨", "濡れた肌", "濡れ肌",
            "谷間", "腰", "ヒップ", "太もも", "肌", "20歳前後", "若い", "少女",
            "erotic", "explicit", "revealing", "young", "girl",
            "20 years old", "body", "hips", "wet skin", "close-up", "full body",
        )
        return any(term in lowered for term in swim_terms) and any(term in lowered for term in risk_terms)

    def _rewrite_prompt_for_image_safety(self, prompt: str, *, force: bool = False) -> str:
        if not force and not self._prompt_has_sexual_safety_risk(prompt):
            return prompt
        text = str(prompt or "")
        replacements = (
            ("胸を触る", "肩先や頬や髪にそっと手を添える"),
            ("胸に触れる", "肩先や頬や髪にそっと手を添える"),
            ("胸を揉む", "抱き寄せる直前の親密な距離感"),
            ("胸を出すような", "胸元の開いた上品な"),
            ("胸を見せるような", "グラマラスなネックラインの"),
            ("胸を出す", "胸元の開いた上品な衣装"),
            ("胸を見せる", "グラマラスなネックラインの衣装"),
            ("トップレス", "胸元の開いた上品な衣装"),
            ("全裸", "衣装をきちんと着用した親密なロマンチックシーン"),
            ("乳首", "上品なネックライン"),
            ("乳輪", "上品なネックライン"),
            ("局部", "衣装のシルエット"),
            ("脱ぐ", "衣装を少し整える仕草"),
            ("脱が", "衣装を少し整える仕草"),
            ("セックス", "親密なロマンチックな雰囲気"),
            ("性交", "親密なロマンチックな雰囲気"),
            ("胸元", "胸元の開いた上品な衣装"),
            ("谷間", "グラマラスなネックライン"),
            ("胸", "胸元の開いた上品な衣装のシルエット"),
            ("裸", "衣装をきちんと着用した親密なロマンチックシーン"),
            ("エッチ", "大人の恋愛らしい甘い緊張感"),
            ("性的", "ロマンティック"),
            ("セクシー", "華やかで大人っぽい"),
            ("エロ", "ロマンティック"),
            ("誘惑的", "魅力的"),
            ("挑発的", "自信のある"),
            ("露骨", "上品"),
            ("露出", "大人っぽい衣装のシルエット"),
            ("濡れた肌", "水しぶきと夏の日差し"),
            ("濡れ肌", "水しぶきと夏の日差し"),
            ("濡れ", "水辺の雰囲気"),
            ("太もも", "脚のライン"),
            ("強調", "自然に表現"),
            ("下着", "インナー風ではない衣装"),
            ("ランジェリー", "ドレス風の衣装"),
            ("水着", "上品で華やかなワンピース型スイムウェアまたはスポーティなツーピースのスイムセット"),
            ("ビキニ", "リゾート向けのスポーティなツーピースのスイムセット"),
            ("touching her breast", "hand near her shoulder or hair"),
            ("touch her breast", "hand near her shoulder or hair"),
            ("sexual act", "romantic tension"),
            ("swimsuit", "tasteful one-piece swimsuit or sporty two-piece swim set"),
            ("bikini", "sporty two-piece swim set with tasteful styling"),
            ("sexy", "glamorous and elegant"),
            ("erotic", "romantic and elegant"),
            ("seductive", "charming and confident"),
            ("revealing", "glamorous neckline with tasteful coverage"),
            ("cleavage", "glamorous neckline"),
            ("lingerie", "dress-like fashion outfit"),
            ("underwear", "fashion outfit"),
            ("topless", "wearing a glamorous neckline outfit"),
            ("nipple", "glamorous neckline"),
            ("areola", "glamorous neckline"),
            ("genitals", "covered outfit silhouette"),
            ("undress", "adjusting her outfit slightly"),
            ("nude", "fully clothed"),
            ("naked", "fully clothed"),
            ("sex", "romantic tension"),
        )
        replacement_lookup = {source: target for source, target in replacements}
        replacement_lookup.update({source.lower(): target for source, target in replacements})
        pattern = re.compile(
            "|".join(re.escape(source) for source, _target in sorted(replacements, key=lambda item: len(item[0]), reverse=True)),
            flags=re.IGNORECASE,
        )
        text = pattern.sub(lambda match: replacement_lookup.get(match.group(0), replacement_lookup.get(match.group(0).lower(), match.group(0))), text)
        text = re.sub(r"20\s*歳\s*前後", "mid-20s adult woman", text)
        text = re.sub(r"20\s*years?\s*old", "mid-20s adult woman", text, flags=re.IGNORECASE)
        return (
            "Safety-conscious image prompt for a visual novel style scene. "
            "Preserve the same character identity, scene intent, emotional mood, and fashion direction, "
            "but avoid wording that emphasizes explicit sexual contact, nudity, nipples, genitals, or fetishized body-part focus. "
            "Do not flatten tasteful adult glamour into generic modest clothing: keep a glamorous neckline, elegant decollete, mature romantic appeal, stylish swimwear, and confident adult fashion when requested. "
            "If the original prompt requested nudity, undressing, touching breasts/chest, or sexual acts, convert it into a safe compromise: "
            "romantic tension, intimate distance, hand near shoulder/upper arm/hair/cheek, protective embrace, suggestive eye contact, "
            "elegant clothing clearly worn, warm lighting, and tasteful visual novel event CG staging. "
            "If the scene involves the sea, beach, pool, or summer vacation, keep requested swimwear recognizable while framing it as cheerful vacation energy: "
            "tasteful one-piece swimsuit, sporty two-piece swim set, coordinated beachwear, resort cover-up, sunlit ocean, "
            "joyful expression, energetic movement, bright atmosphere, sparkling water, and non-sexual editorial fashion. "
            "The character must be clearly an adult woman in her mid-20s or older, confident and wholesome, not young-looking. "
            "Avoid nude/topless/nipple/genital/explicit sexual act wording, hands on breasts/genitals, fetish framing, transparent clothing emphasis, and body-only close-up framing. "
            "Avoid childlike or young-looking wording, suggestive camera angles, "
            "captions, speech bubbles, text, logos, and watermarks.\n\n"
            f"Rewritten scene and costume direction:\n{text}"
        )

    def _rewrite_prompt_for_safety_retry(self, prompt: str) -> str:
        return self._rewrite_prompt_for_image_safety(prompt, force=True)

    def _safety_mode(self) -> str:
        mode = str(os.getenv("IMAGE_PROMPT_SAFETY_MODE") or "both").strip().lower()
        return mode if mode in {"both", "preflight", "retry", "off"} else "both"

    def _allow_safety_retry(self) -> bool:
        return self._safety_mode() in {"both", "retry"}

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
        if "<!DOCTYPE html" in error_message or "<html" in error_message.lower():
            if status_code == 502 or "Bad gateway" in error_message:
                error_message = "Bad gateway. The image API host returned a temporary 502 error."
            else:
                error_message = "The image API returned an HTML error page."

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

    def _xai_aspect_ratio(self, size: Optional[str]) -> str:
        normalized_size = self._normalize_choice(
            size,
            allowed=self.SUPPORTED_SIZES,
            default="1024x1024",
            aliases=self.SIZE_ALIASES,
        )
        return self.XAI_SIZE_ASPECT_RATIOS.get(normalized_size, "auto")

    def _xai_resolution(self, quality: Optional[str]) -> str:
        return "1k"

    def _build_xai_request_payload(
        self,
        prompt: str,
        *,
        negative_prompt: Optional[str] = None,
        size: Optional[str] = None,
        model: Optional[str] = None,
        quality: Optional[str] = None,
    ) -> dict[str, Any]:
        normalized_prompt = self._normalize_prompt(prompt)
        if negative_prompt:
            normalized_prompt = f"{normalized_prompt}\n\nAvoid: {negative_prompt}"
        return {
            "model": self._resolve_model(model, "grok"),
            "prompt": normalized_prompt,
            "n": 1,
            "response_format": "b64_json",
            "aspect_ratio": self._xai_aspect_ratio(size),
            "resolution": self._xai_resolution(quality),
        }

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
                    "Authorization": f"Bearer {self._get_api_key('openai')}",
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
            single_image = len(image_paths) == 1
            for image_path in image_paths:
                mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
                file_handle = open(image_path, "rb")
                file_handles.append(file_handle)
                field_name = "image" if single_image else "image[]"
                files.append((field_name, (os.path.basename(image_path), file_handle, mime_type)))

            def send_request(request_data: dict[str, Any]):
                for _, file_info in files:
                    file_info[1].seek(0)
                response = requests.post(
                    "https://api.openai.com/v1/images/edits",
                    headers={"Authorization": f"Bearer {self._get_api_key('openai')}"},
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
                if (
                    "input_fidelity" in data
                    and (
                        "Unknown parameter: 'input_fidelity'" in message
                        or "does not support the 'input_fidelity' parameter" in message
                    )
                ):
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
        provider: str = "openai",
    ) -> dict[str, Any]:
        data_list = response_json.get("data") or []
        first = data_list[0] if data_list else {}
        return {
            "provider": provider,
            "model": model,
            "prompt": prompt,
            "response_format": response_format,
            "image_base64": first.get("b64_json"),
            "image_url": first.get("url"),
            "revised_prompt": response_json.get("revised_prompt") or first.get("revised_prompt"),
            "raw_response": response_json,
        }

    def _call_xai_images_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(
                "https://api.x.ai/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {self._get_api_key('grok')}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self._resolve_timeout(),
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise RuntimeError("xAI image generation request timed out") from exc
        except requests.HTTPError as exc:
            response = exc.response
            raise RuntimeError(self._extract_error_message(response, "xAI image generation request failed")) from exc
        except requests.RequestException as exc:
            raise RuntimeError("xAI image generation request failed") from exc

    def _image_path_to_data_uri(self, image_path: str) -> str:
        mime_type = mimetypes.guess_type(image_path)[0] or "image/png"
        with open(image_path, "rb") as file_handle:
            encoded = base64.b64encode(file_handle.read()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _call_xai_image_edits_api(self, payload: dict[str, Any], image_paths: list[str]) -> dict[str, Any]:
        request_payload = dict(payload)
        prompt = str(request_payload.get("prompt") or "")
        if image_paths and "Keep the reference outfit unchanged" not in prompt:
            request_payload["prompt"] = (
                "Keep the reference outfit unchanged: preserve the exact clothing design, colors, silhouette, fabric, "
                "accessories, hairstyle, face, body impression, and art style from the reference image. "
                "Do not redesign, simplify, recolor, modernize, or subtly alter the outfit unless the prompt explicitly asks for a costume change. "
                "Only change pose, expression, camera, lighting, and background.\n\n"
                f"{prompt}"
            )
        image_items = [
            {"type": "image_url", "url": self._image_path_to_data_uri(image_path)}
            for image_path in image_paths[:5]
        ]
        if len(image_items) == 1 and request_payload.get("aspect_ratio") not in {None, "", "auto"}:
            # xAI keeps the source image ratio for single-image edits. Sending the same
            # reference twice makes this a multi-image edit, where aspect_ratio is honored.
            request_payload["images"] = [image_items[0], image_items[0]]
        elif len(image_items) == 1:
            request_payload["image"] = image_items[0]
        else:
            request_payload["images"] = image_items
        try:
            response = requests.post(
                "https://api.x.ai/v1/images/edits",
                headers={
                    "Authorization": f"Bearer {self._get_api_key('grok')}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
                timeout=self._resolve_timeout(),
            )
            response.raise_for_status()
            return response.json()
        except requests.Timeout as exc:
            raise RuntimeError("xAI image edit request timed out") from exc
        except FileNotFoundError as exc:
            raise RuntimeError("reference image file was not found") from exc
        except requests.HTTPError as exc:
            response = exc.response
            raise RuntimeError(self._extract_error_message(response, "xAI image edit request failed")) from exc
        except requests.RequestException as exc:
            raise RuntimeError("xAI image edit request failed") from exc

    def _convert_base64_image_to_png(self, image_base64: Optional[str]) -> Optional[str]:
        if not image_base64:
            return image_base64
        try:
            raw_bytes = base64.b64decode(image_base64)
            with Image.open(io.BytesIO(raw_bytes)) as image:
                output = io.BytesIO()
                image.convert("RGBA" if image.mode in {"RGBA", "LA", "P"} else "RGB").save(output, format="PNG")
            return base64.b64encode(output.getvalue()).decode("ascii")
        except Exception:
            return image_base64

    def _normalize_xai_response(
        self,
        response_json: dict[str, Any],
        *,
        prompt: str,
        model: str,
    ) -> dict[str, Any]:
        data_list = response_json.get("data") or []
        first = data_list[0] if data_list else {}
        return {
            "provider": "grok",
            "model": model,
            "prompt": prompt,
            "response_format": "b64_json",
            "image_base64": self._convert_base64_image_to_png(first.get("b64_json")),
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
        provider: Optional[str] = None,
    ) -> dict[str, Any]:
        original_prompt = self._normalize_prompt(prompt)
        normalized_prompt = original_prompt
        safety_preflight = False
        resolved_provider = self._resolve_provider(provider)
        resolved_model = self._resolve_model(model, resolved_provider)
        normalized_input_paths = [path for path in (input_image_paths or []) if path]

        if resolved_provider == "grok":
            xai_payload = self._build_xai_request_payload(
                normalized_prompt,
                negative_prompt=negative_prompt,
                size=size,
                model=resolved_model,
                quality=quality,
            )
            safety_retry = False
            prompt_before_retry = normalized_prompt
            try:
                response_json = (
                    self._call_xai_image_edits_api(xai_payload, normalized_input_paths)
                    if normalized_input_paths
                    else self._call_xai_images_api(xai_payload)
                )
            except RuntimeError as exc:
                if not self._allow_safety_retry() or not self._is_sexual_safety_rejection(exc):
                    raise
                safety_retry = True
                normalized_prompt = self._rewrite_prompt_for_safety_retry(prompt_before_retry)
                xai_payload = self._build_xai_request_payload(
                    normalized_prompt,
                    negative_prompt=negative_prompt,
                    size=size,
                    model=resolved_model,
                    quality=quality,
                )
                response_json = (
                    self._call_xai_image_edits_api(xai_payload, normalized_input_paths)
                    if normalized_input_paths
                    else self._call_xai_images_api(xai_payload)
                )
            result = self._normalize_xai_response(
                response_json,
                prompt=normalized_prompt,
                model=resolved_model,
            )
            result["operation"] = "edit" if normalized_input_paths else "generate"
            result["reference_image_count"] = len(normalized_input_paths)
            result["input_fidelity"] = input_fidelity if normalized_input_paths else None
            result["quality"] = self._xai_resolution(quality)
            result["output_format"] = "png"
            result["background"] = background
            result["aspect_ratio"] = xai_payload.get("aspect_ratio")
            result["safety_preflight"] = safety_preflight
            result["safety_retry"] = safety_retry
            if safety_retry:
                result["prompt_before_safety_retry"] = prompt_before_retry
            return result

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
            safety_retry = False
            prompt_before_retry = normalized_prompt
            try:
                response_json = self._call_openai_image_edits_api(data, normalized_input_paths)
            except RuntimeError as exc:
                if not self._allow_safety_retry() or not self._is_sexual_safety_rejection(exc):
                    raise
                safety_retry = True
                normalized_prompt = self._rewrite_prompt_for_safety_retry(prompt_before_retry)
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
                response_json, prompt=normalized_prompt, model=resolved_model, response_format="b64_json", provider="openai"
            )
            result["operation"] = "edit"
            result["reference_image_count"] = len(normalized_input_paths)
            result["input_fidelity"] = input_fidelity or "low"
            result["quality"] = data.get("quality")
            result["output_format"] = data.get("output_format")
            result["background"] = data.get("background")
            result["safety_preflight"] = safety_preflight
            result["safety_retry"] = safety_retry
            if safety_preflight:
                result["original_prompt_before_safety_preflight"] = original_prompt
            if safety_retry:
                result["prompt_before_safety_retry"] = prompt_before_retry
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
        safety_retry = False
        prompt_before_retry = normalized_prompt
        try:
            response_json = self._call_openai_images_api(payload)
        except RuntimeError as exc:
            if not self._allow_safety_retry() or not self._is_sexual_safety_rejection(exc):
                raise
            safety_retry = True
            normalized_prompt = self._rewrite_prompt_for_safety_retry(prompt_before_retry)
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
            response_json, prompt=normalized_prompt, model=resolved_model, response_format="b64_json", provider="openai"
        )
        result["operation"] = "generate"
        result["reference_image_count"] = 0
        result["input_fidelity"] = None
        result["quality"] = payload.get("quality")
        result["output_format"] = payload.get("output_format")
        result["background"] = payload.get("background")
        result["safety_preflight"] = safety_preflight
        result["safety_retry"] = safety_retry
        if safety_preflight:
            result["original_prompt_before_safety_preflight"] = original_prompt
        if safety_retry:
            result["prompt_before_safety_retry"] = prompt_before_retry
        return result
