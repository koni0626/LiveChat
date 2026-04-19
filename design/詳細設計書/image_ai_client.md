# image_ai_client 詳細設計書

## 1. 対象
- ファイル: `app/clients/image_ai_client.py`
- 目的: 画像生成AI呼び出しクライアントの詳細設計を定義する。

## 2. 参照したソース
### 現状ソース
```python
class ImageAIClient:
    def generate_image(self, prompt: str) -> str:
        raise NotImplementedError
```

### 関連ソース
#### `app/prompts/image_prompt_builder.py`
```python
def build_image_prompt(context: dict) -> str:
    return """# Image Prompt\n\nTODO: build prompt based on context.\n"""
```

#### `app/services/generation_service.py`
```python
class GenerationService:
    VALID_STATUSES = {"queued", "running", "success", "failed"}
    VALID_JOB_TYPES = {"text_generation", "image_generation", "state_extraction"}
    ...
    def enqueue_image_generation(self, scene_id: int, payload: dict | None = None):
        ...
        return self._create_job(scene, job_type="image_generation", payload=payload)
```

### 設計書抜粋
#### アーキテクチャ設計書 13.3
- `text_ai_client.py`
- `image_ai_client.py`
- `generation_service` が生成の流れを制御
- `image_service` が画像保存と asset 登録を行う

#### アーキテクチャ設計書 15.1 基本フロー
1. `scene_state_json` を取得
2. `character_image_rule` を取得
3. 画像生成プロンプトを組み立て
4. 画像生成
5. 保存と採用管理

#### 環境変数
```env
OPENAI_API_KEY=your_openai_api_key
TEXT_AI_MODEL=gpt-5.4-mini
IMAGE_AI_MODEL=gpt-image-1.5
```

## 3. 現状の課題
- クライアントが未実装。
- OpenAI 等の外部APIとの接続仕様がコードにない。
- `generate_image()` の戻り値が `str` だけでは、URL/bytes/path なのか不明瞭。
- 将来複数プロバイダに差し替えるための抽象境界が未定義。

## 4. 役割定義
`ImageAIClient` は以下だけを担当する。
- 画像生成プロバイダへのリクエスト送信
- prompt / negative prompt / size / seed 等の組み立て済み引数を受け取る
- 生成結果をアプリで扱いやすい dict に整形して返す

担当しないこと:
- scene / project 情報の収集
- prompt の生成
- asset 保存
- DB 更新
- 採用フラグ制御

これらは Service 側で担う。

## 5. 公開インターフェース案
### 推奨シグネチャ
```python
def generate_image(
    self,
    prompt: str,
    *,
    negative_prompt: str | None = None,
    size: str | None = None,
    style: str | None = None,
    seed: int | None = None,
    model: str | None = None,
    response_format: str = "b64_json",
) -> dict:
```

### 返却例
```python
{
    "provider": "openai",
    "model": "gpt-image-1.5",
    "prompt": "cinematic sci-fi city...",
    "response_format": "b64_json",
    "image_base64": "...",
    "revised_prompt": "...",
    "raw_response": {...}
}
```

### 最低互換案
現シグネチャ `-> str` を残す場合でも、内部では dict を生成し、`image_base64` だけ返すラッパにする。
ただし設計としては dict 返却の方が望ましい。

## 6. 実装方針
### 6.1 初期実装方針
- OpenAI 系 API を第一候補にする
- `OPENAI_API_KEY` 必須
- `IMAGE_AI_MODEL` 未設定時はアーキテクチャ設計書の `gpt-image-1.5` を既定値にする
- SDK 非依存にしたい場合は HTTP クライアントで `/v1/images/generations` 相当を呼ぶ

### 6.2 provider 抽象化
将来のためにコンストラクタで provider を受けられるようにする。
```python
class ImageAIClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, provider: str = "openai"):
        ...
```

## 7. private helper 設計
### `_get_api_key()`
- 明示引数優先
- 次に `OPENAI_API_KEY`
- 無ければ `RuntimeError`

### `_get_model(model)`
- 引数優先
- 次に `IMAGE_AI_MODEL`
- 無ければ `gpt-image-1.5`

### `_normalize_prompt(prompt)`
- trim
- 空文字禁止

### `_build_request_payload(...)`
例:
```python
{
    "model": "gpt-image-1.5",
    "prompt": prompt,
    "size": size or "1024x1024",
    "response_format": response_format,
}
```
必要に応じて `style`, `seed`, `negative_prompt` を拡張。

### `_call_openai_images_api(payload)`
- HTTP POST 実行
- 失敗時は `RuntimeError` などへ変換

### `_normalize_response(response_json, *, prompt, model, response_format)`
返却 dict を統一する。

## 8. 具体ソース案
```python
import os
from typing import Any

import requests


class ImageAIClient:
    def __init__(self, api_key: str | None = None, model: str | None = None, provider: str = "openai"):
        self._api_key = api_key
        self._model = model
        self._provider = provider

    def _get_api_key(self) -> str:
        api_key = self._api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required")
        return api_key

    def _get_model(self, model: str | None = None) -> str:
        return model or self._model or os.getenv("IMAGE_AI_MODEL") or "gpt-image-1.5"

    def _normalize_prompt(self, prompt: str) -> str:
        value = str(prompt or "").strip()
        if not value:
            raise ValueError("prompt is required")
        return value

    def _build_request_payload(
        self,
        prompt: str,
        *,
        negative_prompt: str | None = None,
        size: str | None = None,
        style: str | None = None,
        seed: int | None = None,
        model: str | None = None,
        response_format: str = "b64_json",
    ) -> dict[str, Any]:
        payload = {
            "model": self._get_model(model),
            "prompt": self._normalize_prompt(prompt),
            "size": size or "1024x1024",
            "response_format": response_format,
        }
        if style:
            payload["style"] = style
        if seed is not None:
            payload["seed"] = seed
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        return payload

    def _call_openai_images_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {self._get_api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def _normalize_response(self, response_json: dict[str, Any], *, prompt: str, model: str, response_format: str) -> dict:
        first = (response_json.get("data") or [{}])[0]
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
        negative_prompt: str | None = None,
        size: str | None = None,
        style: str | None = None,
        seed: int | None = None,
        model: str | None = None,
        response_format: str = "b64_json",
    ) -> dict:
        normalized_prompt = self._normalize_prompt(prompt)
        resolved_model = self._get_model(model)
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
        return self._normalize_response(
            response_json,
            prompt=normalized_prompt,
            model=resolved_model,
            response_format=response_format,
        )
```

## 9. Service 連携イメージ
`generation_service` または `scene_image_service` から以下のように呼ぶ。
```python
prompt = build_image_prompt(context)
result = image_ai_client.generate_image(prompt, size="1024x1024")
image_base64 = result["image_base64"]
```

## 10. エラー方針
- prompt 不正: `ValueError`
- APIキー未設定: `RuntimeError`
- HTTP失敗: `requests.HTTPError` をそのまま or `RuntimeError` に包む
- 期待レスポンス欠落: `RuntimeError("image generation response is invalid")`

## 11. 未解決事項
- OpenAI の最新画像API仕様に合わせて `negative_prompt` 等が非対応の可能性あり。
- 実運用前に使用モデルと payload 仕様を確定する必要がある。
- 画像保存先は client ではなく service 側で行う。

## 12. 結論
`image_ai_client.py` は、**生成済み prompt を受けて外部画像生成APIを呼び、保存前の生成結果 dict を返す薄いクライアント**として設計するのが適切。
