# auth_service 詳細設計書

## 1. 対象
- ファイル: `app/services/auth_service.py`
- 目的: 設計書の認証APIに対応するサービス層の責務を定義する。

## 2. 参照したソース
### 現状ソース
```python
class AuthService:
    def login(self, email: str, password: str):
        raise NotImplementedError

    def logout(self, user_id: int):
        raise NotImplementedError
```

### 関連ソース
#### `app/blueprints/auth/routes.py`
```python
from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash

from app.models import User

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["POST"])
def login():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email")
    password = payload.get("password")

    if not email or not password:
        return jsonify({"data": {"message": "email and password required"}, "meta": {}}), 400

    user = User.query.filter_by(email=email, status="active").first()
    if not user or not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify({"data": {"message": "invalid credentials"}, "meta": {}}), 401

    session["user_id"] = user.id
    session.permanent = True

    return jsonify(
        {
            "data": {
                "user": {"id": user.id, "email": user.email, "display_name": user.display_name}
            },
            "meta": {},
        }
    )
```

#### `app/models/user.py`
```python
from ..extensions import db

from .base import TimestampMixin, SoftDeleteMixin

class User(db.Model, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    display_name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255))
    auth_provider = db.Column(db.String(50), default="local", nullable=False)
    status = db.Column(db.String(50), default="active", nullable=False)
```

### 設計書抜粋
#### API設計書 `8.1 POST /auth/login`
- Request
```json
{
  "email": "user@example.com",
  "password": "password"
}
```
- Response
```json
{
  "data": {
    "token": "jwt-or-random-token",
    "user": {
      "id": 1,
      "email": "user@example.com",
      "display_name": "taka"
    }
  }
}
```

#### API設計書 `8.2 GET /auth/me`
```json
{
  "data": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "taka"
  }
}
```

## 3. 現状の課題
- `AuthService` が未実装で、Blueprint がモデルへ直接アクセスしている。
- 設計書には `token` があるが、現状 Blueprint は session のみで token を返していない。
- `logout(user_id)` という署名だが、実処理は session クリア中心で user_id 必須ではない。
- 認証ロジック、レスポンス整形、エラー方針が Blueprint に埋め込まれている。

## 4. 目的
- 認証処理をサービス層へ集約する。
- Blueprint から DB/パスワード照合ロジックを分離する。
- 設計書上の `token` を返せるよう、トークン生成をサービス責務として定義する。
- 将来 JWT に移行しやすいよう、トークン発行処理を抽象化する。

## 5. 実装方針
### 5.1 責務
`AuthService` は以下を担当する。
- `email` / `password` の入力検証
- `User` の取得
- `password_hash` の照合
- `active` ユーザー判定
- セッショントークンまたは API トークン文字列の生成
- レスポンス用ユーザー情報の整形

Blueprint は以下だけを担当する。
- HTTP の入出力
- Flask `session` への保存/削除
- HTTP ステータスコード変換

### 5.2 公開メソッド案
#### `login(email: str, password: str) -> dict`
返却例:
```python
{
    "token": "generated-token",
    "user": {
        "id": 1,
        "email": "user@example.com",
        "display_name": "taka",
    },
}
```

処理:
1. `email` を trim
2. `password` 必須確認
3. `User.query.filter_by(email=email, status="active").first()`
4. `check_password_hash(user.password_hash, password)`
5. トークン生成
6. dict を返す

#### `logout(user_id: int | None = None) -> dict`
返却例:
```python
{"message": "logged out"}
```

備考:
- 現設計では server-side session のため、サービス層では監査ログや将来の token 無効化フックを担う。
- 当面 user_id は任意引数でよい。

#### `get_current_user(user_id: int) -> dict | None`
返却例:
```python
{
    "id": 1,
    "email": "user@example.com",
    "display_name": "taka",
}
```

## 6. private helper 設計
### `_normalize_email(email)`
- `None` 不可
- `str(email).strip().lower()`
- 空なら `ValueError`

### `_validate_password(password)`
- `None` 不可
- 文字列化はせず、`str` 前提で空文字判定
- 空なら `ValueError`

### `_serialize_user(user)`
```python
{
    "id": user.id,
    "email": user.email,
    "display_name": user.display_name,
}
```

### `_generate_token(user)`
方針:
- 初期実装は `secrets.token_urlsafe(32)` を利用
- 将来 JWT 化する場合はここを差し替える
- `Config.SECRET_KEY` を利用する実装にも切替可能

## 7. 例外/戻り値方針
- 入力不正: `ValueError`
- 認証失敗: `LookupError` または独自 `PermissionError`
  - 推奨: `PermissionError("invalid credentials")`
- 無効ユーザー: `PermissionError`
- `get_current_user` は未存在時 `None`

## 8. 具体ソース案
```python
import secrets

from werkzeug.security import check_password_hash

from ..models import User


class AuthService:
    def _normalize_email(self, email: str) -> str:
        if email is None:
            raise ValueError("email is required")
        value = str(email).strip().lower()
        if not value:
            raise ValueError("email is required")
        return value

    def _validate_password(self, password: str) -> str:
        if password is None or password == "":
            raise ValueError("password is required")
        return password

    def _serialize_user(self, user: User) -> dict:
        return {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
        }

    def _generate_token(self, user: User) -> str:
        return secrets.token_urlsafe(32)

    def login(self, email: str, password: str) -> dict:
        normalized_email = self._normalize_email(email)
        password = self._validate_password(password)

        user = User.query.filter_by(email=normalized_email, status="active").first()
        if not user or not user.password_hash:
            raise PermissionError("invalid credentials")

        if not check_password_hash(user.password_hash, password):
            raise PermissionError("invalid credentials")

        return {
            "token": self._generate_token(user),
            "user": self._serialize_user(user),
        }

    def logout(self, user_id: int | None = None) -> dict:
        return {"message": "logged out"}

    def get_current_user(self, user_id: int):
        if user_id is None:
            return None
        user = User.query.get(user_id)
        if not user or user.status != "active":
            return None
        return self._serialize_user(user)
```

## 9. Blueprint 連携方針
### `POST /auth/login`
Blueprint 側は以下に簡略化できる。
```python
payload = request.get_json(silent=True) or {}
result = auth_service.login(payload.get("email"), payload.get("password"))
session["user_id"] = result["user"]["id"]
session.permanent = True
return jsonify({"data": result, "meta": {}})
```

### `GET /auth/me`
```python
user = auth_service.get_current_user(session.get("user_id"))
if not user:
    session.clear()
    return jsonify({"data": {"user": None}, "meta": {}}), 401
return jsonify({"data": user, "meta": {}})
```

## 10. 未解決事項
- 設計書の `token` を session とどう整合させるか。
  - 当面は「クライアント表示用 token」を返すだけでもよい。
  - 厳密運用するなら JWT または DB 保存型トークンテーブルが必要。
- `logout()` で usage_log 等を残すかは別途判断。

## 11. 結論
`auth_service.py` は、まず **ローカル認証 + token文字列生成 + user整形** を提供する実装にする。Blueprint から直接 `User.query` している現状をサービスへ寄せることで、設計書準拠と責務分離の両方を満たせる。
