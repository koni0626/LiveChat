from __future__ import annotations

from typing import Any

from ..api import ApiError
from ..extensions import db
from ..models import PointTransaction, User
from ..utils import json_util


class InsufficientPointsError(ApiError):
    def __init__(self, *, required_points: int, points_balance: int):
        super().__init__(
            "ポイントが不足しています",
            status_code=402,
            code="insufficient_points",
            meta={
                "required_points": required_points,
                "points_balance": points_balance,
            },
        )


class PointService:
    INITIAL_POINTS = 3000
    LIVE_CHAT_MESSAGE_POINTS = 15
    IMAGE_GENERATION_POINTS = 30

    def _serialize_detail(self, detail: dict[str, Any] | None) -> str | None:
        if not detail:
            return None
        return json_util.dumps(detail)

    def get_balance(self, user: User | int) -> int:
        if isinstance(user, User):
            value = getattr(user, "points_balance", None)
            return int(value if value is not None else 0)
        row = User.query.get(int(user))
        return int(getattr(row, "points_balance", 0) or 0) if row else 0

    def ensure_balance(self, user: User, amount: int) -> None:
        balance = self.get_balance(user)
        if balance < int(amount):
            raise InsufficientPointsError(required_points=int(amount), points_balance=balance)

    def grant_initial_points(self, user: User) -> PointTransaction:
        user.points_balance = self.INITIAL_POINTS
        transaction = PointTransaction(
            user_id=user.id,
            action_type="initial_grant",
            points_delta=self.INITIAL_POINTS,
            balance_after=user.points_balance,
            status="success",
            detail_json=self._serialize_detail({"reason": "new_user_bonus"}),
        )
        db.session.add(user)
        db.session.add(transaction)
        db.session.commit()
        return transaction

    def charge(
        self,
        user: User,
        *,
        amount: int,
        action_type: str,
        project_id: int | None = None,
        session_id: int | None = None,
        message_id: int | None = None,
        image_id: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> PointTransaction:
        amount = int(amount)
        if amount <= 0:
            raise ValueError("amount must be positive")
        row = User.query.get(user.id)
        if not row or not row.is_active_user:
            raise ValueError("user is not active")
        balance = int(row.points_balance or 0)
        if balance < amount:
            raise InsufficientPointsError(required_points=amount, points_balance=balance)
        row.points_balance = balance - amount
        transaction = PointTransaction(
            user_id=row.id,
            project_id=project_id,
            action_type=action_type,
            points_delta=-amount,
            balance_after=row.points_balance,
            status="success",
            session_id=session_id,
            message_id=message_id,
            image_id=image_id,
            detail_json=self._serialize_detail(detail),
        )
        db.session.add(row)
        db.session.add(transaction)
        db.session.commit()
        return transaction

    def test_purchase(
        self,
        user: User,
        *,
        amount: int,
        detail: dict[str, Any] | None = None,
    ) -> PointTransaction:
        amount = int(amount)
        if amount <= 0:
            raise ValueError("amount must be positive")
        if amount > 100000:
            raise ValueError("amount must be <= 100000")
        row = User.query.get(user.id)
        if not row or not row.is_active_user:
            raise ValueError("user is not active")
        row.points_balance = int(row.points_balance or 0) + amount
        transaction = PointTransaction(
            user_id=row.id,
            action_type="point_purchase_test",
            points_delta=amount,
            balance_after=row.points_balance,
            status="success",
            detail_json=self._serialize_detail({"source": "test_purchase", **(detail or {})}),
        )
        db.session.add(row)
        db.session.add(transaction)
        db.session.commit()
        return transaction
