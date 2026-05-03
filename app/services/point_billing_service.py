from __future__ import annotations

from typing import Any

from ..models import User
from .point_service import PointService


class PointBillingService:
    def __init__(self, point_service: PointService | None = None):
        self._point_service = point_service or PointService()

    def ensure_chat_message_balance(self, user: User) -> None:
        self._point_service.ensure_balance(user, PointService.LIVE_CHAT_MESSAGE_POINTS)

    def ensure_image_generation_balance(self, user: User) -> None:
        self._point_service.ensure_balance(user, PointService.IMAGE_GENERATION_POINTS)

    def charge_chat_message(
        self,
        user: User,
        *,
        project_id: int,
        session_id: int,
        result: dict[str, Any] | None,
        detail: dict[str, Any] | None = None,
    ):
        transaction = self._point_service.charge(
            user,
            amount=PointService.LIVE_CHAT_MESSAGE_POINTS,
            action_type="live_chat_message",
            project_id=project_id,
            session_id=session_id,
            message_id=self.result_message_id(result),
            detail=detail,
        )
        return self.attach_points(result, transaction)

    def charge_image_generation(
        self,
        user: User,
        *,
        project_id: int,
        session_id: int,
        result: dict[str, Any] | None,
        action_type: str = "image_generation",
        detail: dict[str, Any] | None = None,
    ):
        transaction = self._point_service.charge(
            user,
            amount=PointService.IMAGE_GENERATION_POINTS,
            action_type=action_type,
            project_id=project_id,
            session_id=session_id,
            image_id=self.result_image_id(result),
            detail=detail,
        )
        return self.attach_points(result, transaction)

    def attach_points(self, result, transaction):
        if isinstance(result, dict):
            result["points"] = {
                "delta": transaction.points_delta,
                "balance": transaction.balance_after,
                "action_type": transaction.action_type,
            }
        return result

    def result_image_id(self, result) -> int | None:
        if not isinstance(result, dict):
            return None
        for key in ("image", "initial_image", "costume", "photo", "session_image", "generated_image"):
            value = result.get(key)
            if isinstance(value, dict) and value.get("id"):
                return int(value["id"])
        if result.get("image_id"):
            return int(result["image_id"])
        images = result.get("images")
        if isinstance(images, list) and images:
            first = images[0]
            if isinstance(first, dict) and first.get("id"):
                return int(first["id"])
        return None

    def result_message_id(self, result) -> int | None:
        if not isinstance(result, dict):
            return None
        for key in ("message", "assistant_message", "user_message"):
            value = result.get(key)
            if isinstance(value, dict) and value.get("id"):
                return int(value["id"])
        if result.get("message_id"):
            return int(result["message_id"])
        messages = result.get("messages")
        if isinstance(messages, list) and messages:
            last = messages[-1]
            if isinstance(last, dict) and last.get("id"):
                return int(last["id"])
        return None
