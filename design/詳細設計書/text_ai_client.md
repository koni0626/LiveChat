# text_ai_client 詳細設計書

## 1. 対象
- ファイル: `app/clients/text_ai_client.py`
- 目的: シーン本文生成・状態抽出に使うテキスト生成クライアントの詳細設計を定義する。

## 2. 参照したソース
### 現状ソース
```python
class TextAIClient:
    def generate_scene(self, prompt: str) -> str:
        raise NotImplementedError
```

### 関連ソース
#### `app/prompts/scene_prompt_builder.py`
```python
def build_scene_prompt(context: dict) -> str:
    return """# Scene Prompt\n\nTODO: build prompt based on context.\n"""
```

#### `app/services/generation_service.py`
```python
class GenerationService:
    VALID_JOB_TYPES = {"text_generation", "image_generation", "state_extraction"}
```

### 設計書抜粋
#### アーキテクチャ設計書 13.2
1. シーン本文生成
2. 状態JSON抽出
3. 画像生成プロンプト作成
4. 画像生成
5. 保存と採用管理

#### アーキテクチャ設計書 14.1
1. scene 情報を取得
2. world / character / outline 情報を集約
3. scene 生成プロンプトを組み立て
4. テキスト生成AI を呼ぶ
5. scene_version を保存

#### アーキテクチャ設計書 14.2
1. scene 本文を取得
2. 状態抽出プロンプトを組み立て
3. 状態JSON を生成
4. scene.scene_state_json に保存

#### 環境変数
```env
OPENAI_API_KEY=your_openai_api_key
TEXT_AI_MODEL=gpt-5.4-mini
IMAGE_AI_MODEL=gpt-image-1.5
```

## 3. 現状の課題
- `generate_scene()` しかなく、状態抽出ユースケースを表現できない。
- 戻り値が `str` のみで、raw response / usage / model 情報が失われる。
- 生成 job の監査に必要な request / response 保存に向いていない。

## 4. 役割定義
`TextAIClient` は以下を担当する。
- 生成済み prompt を受け取って LLM を呼ぶ
- シーン本文生成
- 状態JSON抽出
- 必要に応じて汎用 completion 呼び出し
- usage, model, raw response の正規化

担当しないこと:
- prompt の組み立て
- scene_version 保存
- generated_candidate 保存
- job 状態更新

## 5. 公開インターフェース案
### 5.1 汎用メソッド
```python
def generate_text(
    self,
    prompt: str,
    *,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    response_format: dict | None = None,
) -> dict:
```

返却例:
```python
{
    "provider": "openai",
    "model": "gpt-5.4-mini",
    "text": "生成本文...",
    "usage": {"input_tokens": 100, "output_tokens": 300},
    "raw_response": {...}
}
```

### 5.2 シーン生成専用ラッパ
```python
def generate_scene(self, prompt: str, *, model: str | None = None) -> dict:
```
- 内部で `generate_text()` を呼ぶ
- scene 本文向け既定 temperature を与える

### 5.3 状態抽出専用ラッパ
```python
def extract_state_json(self, prompt: str, *, model: str | None = None) -> dict:
```
- JSON出力を強く要求する
- 戻り値には `text` と `parsed_json` を含める

## 6. 実装方針
### 6.1 モデル解決
- 引数 `model`
- `self._model`
- 環境変数 `TEXT_AI_MODEL`
- fallback `gpt-5.4-mini`

### 6.2 provider
初期実装は OpenAI を想定。
将来の Claude 等差し替えのため `provider` 引数を持つ。

### 6.3 OpenAI 呼び出し
- Responses API または Chat Completions API を利用
- ここでは汎用性のため HTTP ベース例を採用

## 7. private helper 設計
### `_get_api_key()`
- `OPENAI_API_KEY` を取得
- 無ければ `RuntimeError`

### `_get_model(model)`
- 既定モデル解決

### `_normalize_prompt(prompt)`
- trim
- 空禁止

### `_build_messages(prompt, system_prompt=None)`
```python
[
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": prompt},
]
```

### `_call_openai_chat(payload)`
- HTTP POST
- タイムアウト付き

### `_extract_text(response_json)`
- OpenAI レスポンス差異を吸収して本文文字列を返す

### `_extract_usage(response_json)`
- token usage を dict 化

### `_try_parse_json(text)`
- JSON文字列なら dict/list を返す
- 失敗時 `None`

## 8. 具体ソース案
```python
import json
import os
from typing import Any

import requests


class TextAIClient:
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
        return model or self._model or os.getenv("TEXT_AI_MODEL") or "gpt-5.4-mini"

    def _normalize_prompt(self, prompt: str) -> str:
        value = str(prompt or "").strip()
        if not value:
            raise ValueError("prompt is required")
        return value

    def _build_messages(self, prompt: str, system_prompt: str | None = None) -> list[dict[str, str]]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _call_openai_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._get_api_key()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def _extract_text(self, response_json: dict[str, Any]) -> str:
        choices = response_json.get("choices") or []
        if not choices:
            raise RuntimeError("text generation response is invalid")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("text generation response is invalid")
        return content.strip()

    def _extract_usage(self, response_json: dict[str, Any]) -> dict[str, Any] | None:
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
        system_prompt: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> dict:
        normalized_prompt = self._normalize_prompt(prompt)
        resolved_model = self._get_model(model)
        payload = {
            "model": resolved_model,
            "messages": self._build_messages(normalized_prompt, system_prompt),
        }
        if temperature is not None:
            payload["temperature"] = temperature
        if response_format is not None:
            payload["response_format"] = response_format

        response_json = self._call_openai_chat(payload)
        text = self._extract_text(response_json)
        return {
            "provider": self._provider,
            "model": resolved_model,
            "text": text,
            "usage": self._extract_usage(response_json),
            "raw_response": response_json,
        }

    def generate_scene(self, prompt: str, *, model: str | None = None) -> dict:
        return self.generate_text(prompt, model=model, temperature=0.9)

    def extract_state_json(self, prompt: str, *, model: str | None = None) -> dict:
        result = self.generate_text(
            prompt,
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        result["parsed_json"] = self._try_parse_json(result["text"])
        return result
```

## 9. generation_service 連携イメージ
```python
scene_prompt = build_scene_prompt(context)
scene_result = text_ai_client.generate_scene(scene_prompt)
scene_text = scene_result["text"]

state_result = text_ai_client.extract_state_json(state_prompt)
state_json = state_result["parsed_json"]
```

## 10. エラー方針
- prompt 不正: `ValueError`
- APIキー未設定: `RuntimeError`
- HTTP失敗: `requests.HTTPError`
- レスポンス異常: `RuntimeError`
- JSONパース失敗: `parsed_json=None` として返す

## 11. 未解決事項
- OpenAI Responses API を使うか Chat Completions API を使うかは本実装時に統一要。
- 長文生成時の max_tokens 制御を必要に応じて追加。
- ストリーミングは初期段階では未対応でよい。

## 12. 結論
`text_ai_client.py` は、**scene生成と state抽出の両方を支える汎用テキスト生成クライアント**として設計し、戻り値は単なる文字列ではなく `text + usage + raw_response` を含む dict に拡張するのが適切。
