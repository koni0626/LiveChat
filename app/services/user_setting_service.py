from __future__ import annotations

from flask import has_request_context, request

from ..api import UnauthorizedError, ValidationError
from ..extensions import db
from ..models import User, UserSetting


class UserSettingService:
    DEFAULTS = {
        "text_ai_model": "gpt-5.4-mini",
        "image_ai_provider": "openai",
        "image_ai_model": "gpt-image-2",
        "default_quality": "medium",
        "default_size": "1024x1024",
        "prefer_portrait_on_mobile": False,
        "autosave_interval": "off",
    }
    PROVIDER_DEFAULT_MODELS = {
        "openai": "gpt-image-2",
        "grok": "grok-imagine-image",
    }
    VALID_IMAGE_PROVIDERS = {"openai", "grok"}
    VALID_QUALITIES = {"low", "medium", "high"}
    VALID_SIZES = {"1024x1024", "1024x1536", "1536x1024"}
    VALID_AUTOSAVE_INTERVALS = {"off", "30", "60"}

    def _get_active_user(self, user_id: int | None) -> User:
        if not user_id:
            raise UnauthorizedError()
        user = User.query.get(user_id)
        if not user or not user.is_active_user:
            raise UnauthorizedError()
        return user

    def _get_or_create(self, user_id: int) -> UserSetting:
        setting = UserSetting.query.filter_by(user_id=user_id).first()
        if setting:
            return setting
        setting = UserSetting(user_id=user_id, **self.DEFAULTS)
        db.session.add(setting)
        db.session.commit()
        return setting

    def _get_global_setting(self) -> UserSetting | None:
        owner = (
            User.query.filter_by(role="superuser", status="active")
            .filter(User.deleted_at.is_(None))
            .order_by(User.id.asc())
            .first()
        )
        if owner:
            return self._get_or_create(owner.id)
        return UserSetting.query.order_by(UserSetting.user_id.asc()).first()

    def _serialize(self, setting: UserSetting) -> dict:
        return {
            "user_id": setting.user_id,
            "text_ai_model": setting.text_ai_model,
            "image_ai_provider": getattr(setting, "image_ai_provider", None) or self.DEFAULTS["image_ai_provider"],
            "image_ai_model": setting.image_ai_model,
            "default_quality": setting.default_quality,
            "default_size": setting.default_size,
            "prefer_portrait_on_mobile": bool(getattr(setting, "prefer_portrait_on_mobile", False)),
            "autosave_interval": setting.autosave_interval,
            "available_options": {
                "image_providers": sorted(self.VALID_IMAGE_PROVIDERS),
                "provider_default_models": dict(self.PROVIDER_DEFAULT_MODELS),
                "qualities": sorted(self.VALID_QUALITIES),
                "sizes": sorted(self.VALID_SIZES),
                "autosave_intervals": sorted(self.VALID_AUTOSAVE_INTERVALS, key=lambda item: (item == "off", item)),
            },
        }

    def _normalize_string(self, payload: dict, key: str) -> str:
        value = payload.get(key, self.DEFAULTS[key])
        value = str(value or "").strip()
        if not value:
            raise ValidationError(f"{key} is required")
        return value

    def _normalize_image_model_for_provider(self, provider: str, model: str | None) -> str:
        value = str(model or "").strip()
        if provider == "grok":
            if not value or value.startswith(("gpt-", "dall-e")):
                return self.PROVIDER_DEFAULT_MODELS["grok"]
            return value
        if provider == "openai" and value.startswith("grok-"):
            return self.PROVIDER_DEFAULT_MODELS["openai"]
        return value or self.PROVIDER_DEFAULT_MODELS.get(provider, self.DEFAULTS["image_ai_model"])

    def _normalize_bool(self, value) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _is_mobile_request(self) -> bool:
        if not has_request_context():
            return False
        user_agent = (request.headers.get("User-Agent") or "").lower()
        return any(token in user_agent for token in ("iphone", "android", "mobile", "ipad"))

    def get_settings(self, user_id: int | None) -> dict:
        user = self._get_active_user(user_id)
        setting = self._get_or_create(user.id)
        return self._serialize(setting)

    def get_global_settings(self) -> dict:
        setting = self._get_global_setting()
        if not setting:
            return self._serialize_defaults()
        return self._serialize(setting)

    def _serialize_defaults(self) -> dict:
        return {
            "user_id": None,
            "text_ai_model": self.DEFAULTS["text_ai_model"],
            "image_ai_provider": self.DEFAULTS["image_ai_provider"],
            "image_ai_model": self.DEFAULTS["image_ai_model"],
            "default_quality": self.DEFAULTS["default_quality"],
            "default_size": self.DEFAULTS["default_size"],
            "prefer_portrait_on_mobile": bool(self.DEFAULTS["prefer_portrait_on_mobile"]),
            "autosave_interval": self.DEFAULTS["autosave_interval"],
            "available_options": {
                "image_providers": sorted(self.VALID_IMAGE_PROVIDERS),
                "provider_default_models": dict(self.PROVIDER_DEFAULT_MODELS),
                "qualities": sorted(self.VALID_QUALITIES),
                "sizes": sorted(self.VALID_SIZES),
                "autosave_intervals": sorted(self.VALID_AUTOSAVE_INTERVALS, key=lambda item: (item == "off", item)),
            },
        }

    def update_settings(self, user_id: int | None, payload: dict | None) -> dict:
        user = self._get_active_user(user_id)
        setting = self._get_or_create(user.id)
        return self._update_setting(setting, payload)

    def update_global_settings(self, payload: dict | None) -> dict:
        setting = self._get_global_setting()
        if not setting:
            raise UnauthorizedError()
        return self._update_setting(setting, payload)

    def _update_setting(self, setting: UserSetting, payload: dict | None) -> dict:
        payload = dict(payload or {})
        text_ai_model = self._normalize_string(payload, "text_ai_model")
        image_ai_provider = self._normalize_string(payload, "image_ai_provider").lower()
        image_ai_model = self._normalize_string(payload, "image_ai_model")
        default_quality = self._normalize_string(payload, "default_quality")
        default_size = self._normalize_string(payload, "default_size")
        prefer_portrait_on_mobile = self._normalize_bool(payload.get("prefer_portrait_on_mobile", False))
        autosave_interval = self._normalize_string(payload, "autosave_interval")

        if image_ai_provider not in self.VALID_IMAGE_PROVIDERS:
            raise ValidationError("image_ai_provider is invalid")
        image_ai_model = self._normalize_image_model_for_provider(image_ai_provider, image_ai_model)
        if default_quality not in self.VALID_QUALITIES:
            raise ValidationError("default_quality is invalid")
        if default_size not in self.VALID_SIZES:
            raise ValidationError("default_size is invalid")
        if autosave_interval not in self.VALID_AUTOSAVE_INTERVALS:
            raise ValidationError("autosave_interval is invalid")

        setting.text_ai_model = text_ai_model
        setting.image_ai_provider = image_ai_provider
        setting.image_ai_model = image_ai_model
        setting.default_quality = default_quality
        setting.default_size = default_size
        setting.prefer_portrait_on_mobile = prefer_portrait_on_mobile
        setting.autosave_interval = autosave_interval
        db.session.commit()
        return self._serialize(setting)

    def apply_image_generation_settings(self, user_id: int | None, payload: dict | None = None) -> dict:
        settings = self.get_settings(user_id)
        return self._apply_image_generation_settings(settings, payload)

    def apply_global_image_generation_settings(self, payload: dict | None = None) -> dict:
        settings = self.get_global_settings()
        return self._apply_image_generation_settings(settings, payload)

    def _apply_image_generation_settings(self, settings: dict, payload: dict | None = None) -> dict:
        options = dict(payload or {})
        if "provider" not in options and options.get("image_ai_provider"):
            options["provider"] = options.get("image_ai_provider")
        if "model" not in options and options.get("image_ai_model"):
            options["model"] = options.get("image_ai_model")
        options.setdefault("provider", settings.get("image_ai_provider") or self.DEFAULTS["image_ai_provider"])
        options.setdefault("model", settings.get("image_ai_model") or self.DEFAULTS["image_ai_model"])
        options["provider"] = str(options.get("provider") or "openai").strip().lower()
        options["model"] = self._normalize_image_model_for_provider(options["provider"], options.get("model"))
        options.setdefault("quality", settings.get("default_quality") or self.DEFAULTS["default_quality"])
        options.setdefault("size", settings.get("default_size") or self.DEFAULTS["default_size"])
        if self._normalize_bool(settings.get("prefer_portrait_on_mobile")) and self._is_mobile_request():
            options["size"] = "1024x1536"
        return options

    def reset_settings(self, user_id: int | None) -> dict:
        user = self._get_active_user(user_id)
        setting = self._get_or_create(user.id)
        return self._reset_setting(setting)

    def reset_global_settings(self) -> dict:
        setting = self._get_global_setting()
        if not setting:
            raise UnauthorizedError()
        return self._reset_setting(setting)

    def _reset_setting(self, setting: UserSetting) -> dict:
        for key, value in self.DEFAULTS.items():
            setattr(setting, key, value)
        db.session.commit()
        return self._serialize(setting)
