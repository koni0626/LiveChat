# AIノベルゲームツクール API設計書

## 1. 目的

本書は、AIノベルゲームツクールにおける API の設計方針、エンドポイント、リクエスト/レスポンス仕様、エラー設計、認証方針を定義する。

本システムは、作品管理、キャラクター管理、世界観管理、シーン生成、画像生成、プレビュー、エクスポートを扱うため、**制作UIから一貫して呼び出せるアプリケーション API** を提供する。

---

## 2. 前提

### 2.1 APIスタイル

* HTTP + JSON ベースの REST API を基本とする
* 一部の非同期処理はジョブ API として扱う
* MVPではシンプルな構成を優先する

### 2.2 想定利用者

* Webフロントエンド
* 将来的なデスクトップ版クライアント
* 内部の管理画面

### 2.3 ベースパス

* `/api/v1`

### 2.4 文字コード

* UTF-8

### 2.5 日時形式

* ISO 8601 文字列

---

## 3. 設計方針

### 3.1 基本方針

* リソース単位で URI を設計する
* UI がそのまま使いやすい粒度の API を用意する
* AI生成系は非同期ジョブで管理できるようにする
* 生成結果の採用/却下ができるよう、履歴を前提にする
* 画像生成は asset と generation_job を分離する

### 3.2 命名方針

* パスは複数形を使う

  * `/projects`
  * `/characters`
  * `/scenes`
* JSON キーは snake_case
* 真偽値は boolean
* ID は integer

### 3.3 HTTPメソッド

* GET: 取得
* POST: 新規作成 / アクション実行
* PUT: 全体更新
* PATCH: 部分更新
* DELETE: 論理削除

---

## 4. 認証・認可

## 4.1 認証方式

MVPでは以下のいずれかを採用する。

* セッション認証
* Bearer Token 認証

本設計書では、将来拡張しやすいよう **Bearer Token 認証** を前提とする。

### ヘッダ例

```http
Authorization: Bearer <token>
```

## 4.2 認可方針

* ユーザーは自分の project のみ参照・更新可能
* project 配下のリソースは project 所有者のみ操作可能
* 将来的に共同編集を入れる場合は project_member テーブル拡張で対応

---

## 5. 共通レスポンス形式

## 5.1 成功レスポンス

```json
{
  "data": {},
  "meta": {}
}
```

## 5.2 エラーレスポンス

```json
{
  "error": {
    "code": "validation_error",
    "message": "title is required",
    "details": {
      "field": "title"
    }
  }
}
```

## 5.3 ページング

一覧系 API は以下形式を返す。

```json
{
  "data": [],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 120,
    "total_pages": 6
  }
}
```

---

## 6. エラーコード設計

### 共通エラーコード

* `unauthorized`
* `forbidden`
* `not_found`
* `validation_error`
* `conflict`
* `generation_failed`
* `internal_server_error`

### HTTPステータス対応

* 400: validation_error
* 401: unauthorized
* 403: forbidden
* 404: not_found
* 409: conflict
* 422: generation_failed
* 500: internal_server_error

---

## 7. API一覧

### 認証

* POST `/auth/register`
* POST `/auth/login`
* POST `/auth/logout`
* GET `/auth/me`

### 作品

* GET `/projects`
* POST `/projects`
* GET `/projects/{project_id}`
* PATCH `/projects/{project_id}`
* DELETE `/projects/{project_id}`

### 世界観

* GET `/projects/{project_id}/world`
* PUT `/projects/{project_id}/world`

### 用語辞書

* GET `/projects/{project_id}/glossary`
* POST `/projects/{project_id}/glossary`
* PATCH `/glossary/{term_id}`
* DELETE `/glossary/{term_id}`

### キャラクター

* GET `/projects/{project_id}/characters`
* POST `/projects/{project_id}/characters`
* GET `/characters/{character_id}`
* PATCH `/characters/{character_id}`
* DELETE `/characters/{character_id}`

### キャラクター画像ルール

* GET `/characters/{character_id}/image-rule`
* PUT `/characters/{character_id}/image-rule`

### ストーリー骨子

* GET `/projects/{project_id}/story-outline`
* PUT `/projects/{project_id}/story-outline`
* POST `/projects/{project_id}/story-outline/generate`

### 章

* GET `/projects/{project_id}/chapters`
* POST `/projects/{project_id}/chapters`
* PATCH `/chapters/{chapter_id}`
* DELETE `/chapters/{chapter_id}`

### シーン

* GET `/projects/{project_id}/scenes`
* POST `/projects/{project_id}/scenes`
* GET `/scenes/{scene_id}`
* PATCH `/scenes/{scene_id}`
* DELETE `/scenes/{scene_id}`
* POST `/scenes/{scene_id}/generate`
* POST `/scenes/{scene_id}/extract-state`
* POST `/scenes/{scene_id}/fix`
* POST `/scenes/{scene_id}/unfix`

### シーン選択肢

* GET `/scenes/{scene_id}/choices`
* POST `/scenes/{scene_id}/choices`
* PATCH `/scene-choices/{choice_id}`
* DELETE `/scene-choices/{choice_id}`

### シーン履歴

* GET `/scenes/{scene_id}/versions`
* POST `/scenes/{scene_id}/versions/{version_id}/adopt`

### 画像生成

* GET `/scenes/{scene_id}/images`
* POST `/scenes/{scene_id}/images/generate`
* POST `/scene-images/{scene_image_id}/select`
* POST `/scene-images/{scene_image_id}/regenerate`

### アセット

* POST `/assets/upload`
* GET `/assets/{asset_id}`

### ジョブ

* GET `/jobs/{job_id}`
* GET `/projects/{project_id}/jobs`

### プレビュー

* GET `/projects/{project_id}/preview`
* GET `/projects/{project_id}/preview/scenes/{scene_id}`

### エクスポート

* POST `/projects/{project_id}/exports`
* GET `/projects/{project_id}/exports`
* GET `/exports/{export_job_id}`

---

## 8. 認証API

## 8.1 POST /auth/register

### 目的

新規ユーザーを作成し、そのままログイン状態へ入る。

### Request

```json
{
  "email": "user@example.com",
  "display_name": "taka",
  "password": "password"
}
```

### Response

```json
{
  "data": {
    "token": "jwt-or-random-token",
    "auth_mode": "session",
    "user": {
      "id": 1,
      "email": "user@example.com",
      "display_name": "taka",
      "status": "active",
      "auth_provider": "local"
    }
  }
}
```

### バリデーション

* `email` 必須
* `display_name` 必須
* `password` 必須
* 既存メールアドレスとの重複不可

---

## 8.2 POST /auth/login

### 目的

ログインする。

### Request

```json
{
  "email": "user@example.com",
  "password": "password"
}
```

### Response

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

---

## 8.3 GET /auth/me

### 目的

現在ログイン中のユーザー情報を取得する。

### Response

```json
{
  "data": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "taka"
  }
}
```

---

## 9. 作品API

## 9.1 GET /projects

### 目的

作品一覧を取得する。

### Query

* `page`
* `per_page`
* `status`
* `keyword`

### Response

```json
{
  "data": [
    {
      "id": 10,
      "title": "ラプラスシティ探索記",
      "genre": "SF",
      "status": "editing",
      "updated_at": "2026-04-18T16:00:00+09:00"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 1,
    "total_pages": 1
  }
}
```

---

## 9.2 POST /projects

### 目的

新規作品を作成する。

### Request

```json
{
  "title": "ラプラスシティ探索記",
  "genre": "SF",
  "summary": "ノアが案内する未来都市探索ノベル",
  "play_time_minutes": 30,
  "project_type": "exploration"
}
```

### Response

```json
{
  "data": {
    "id": 10,
    "title": "ラプラスシティ探索記",
    "status": "draft"
  }
}
```

---

## 9.3 GET /projects/{project_id}

### 目的

作品詳細を取得する。

### Response

```json
{
  "data": {
    "id": 10,
    "title": "ラプラスシティ探索記",
    "genre": "SF",
    "summary": "ノアが案内する未来都市探索ノベル",
    "project_type": "exploration",
    "status": "editing",
    "world_id": 3
  }
}
```

---

## 9.4 PATCH /projects/{project_id}

### 目的

作品情報を部分更新する。

### Request

```json
{
  "title": "ラプラスシティ観測録",
  "status": "editing"
}
```

---

## 10. 世界観API

## 10.1 GET /projects/{project_id}/world

### 目的

作品の世界観設定を取得する。

### Response

```json
{
  "data": {
    "id": 3,
    "name": "ラプラスシティ",
    "era_description": "西暦5026年の火星都市",
    "technology_level": "超高度AI社会",
    "tone": "神秘的で未来的"
  }
}
```

---

## 10.2 PUT /projects/{project_id}/world

### 目的

世界観設定を作成または更新する。

### Request

```json
{
  "name": "ラプラスシティ",
  "era_description": "西暦5026年の火星都市",
  "technology_level": "超高度AI社会",
  "social_structure": "ヒューマノイド中心社会",
  "tone": "神秘的で未来的",
  "overview": "観測と演算で成り立つ都市"
}
```

---

## 11. キャラクターAPI

## 11.1 GET /projects/{project_id}/characters

### 目的

作品のキャラクター一覧を取得する。

### Response

```json
{
  "data": [
    {
      "id": 21,
      "name": "ノア",
      "role": "案内役",
      "is_guide": true,
      "base_asset_id": 55
    }
  ]
}
```

---

## 11.2 POST /projects/{project_id}/characters

### 目的

キャラクターを作成する。

### Request

```json
{
  "name": "ノア",
  "role": "案内役",
  "first_person": "わたし",
  "personality": "穏やかで優しい",
  "speech_style": "柔らかい口調",
  "appearance_summary": "ショートボブ、青い発光インカム、人間の耳",
  "base_asset_id": 55,
  "is_guide": true
}
```

### 備考

* `base_asset_id` はキャラクターの基準画像を指す
* 基準画像は画像生成時に reference image として利用できる

---

## 11.3 PATCH /characters/{character_id}

### 目的

キャラクターを更新する。

### Request

```json
{
  "speech_sample": "こんばんは。わたしはノア。",
  "ng_rules": "乱暴な口調は禁止"
}
```

---

## 11.4 PUT /characters/{character_id}/image-rule

### 目的

キャラクター画像固定ルールを更新する。

### Request

```json
{
  "hair_rule": "short brown bob",
  "ear_rule": "human ears",
  "accessory_rule": "glowing blue earpiece",
  "style_rule": "soft transparent anime style",
  "default_quality": "low",
  "default_size": "1024x1024",
  "prompt_prefix": "based on the reference image"
}
```

### 備考

* `prompt_prefix` には `based on the reference image` など、参照画像前提の指示を入れられる
* 実装では `character.base_asset_id` が存在する場合、image edit / reference image ベースの生成に利用できる

---

## 12. ストーリー骨子API

## 12.1 GET /projects/{project_id}/story-outline

### 目的

作品の骨子を取得する。

## 12.2 PUT /projects/{project_id}/story-outline

### 目的

骨子を保存する。

### Request

```json
{
  "premise": "ノアが未来都市を案内する探索ノベル",
  "main_goal": "都市の秘密を知る",
  "branching_policy": "探索型で軽い分岐",
  "ending_policy": "true, normal, bad の3種"
}
```

## 12.3 POST /projects/{project_id}/story-outline/generate

### 目的

入力条件から骨子案を自動生成する。

### Request

```json
{
  "theme": "未来都市探索",
  "guide_character_id": 21,
  "chapter_count": 3,
  "ending_count": 3
}
```

### Response

```json
{
  "data": {
    "job_id": 1001,
    "status": "queued"
  }
}
```

---

## 13. 章API

## 13.1 GET /projects/{project_id}/chapters

### 目的

章一覧を取得する。

## 13.2 POST /projects/{project_id}/chapters

### 目的

章を追加する。

### Request

```json
{
  "chapter_no": 1,
  "title": "中央演算塔",
  "summary": "ノアに導かれて塔へ向かう",
  "objective": "都市の中枢を知る"
}
```

## 13.3 PATCH /chapters/{chapter_id}

### 目的

章情報を更新する。

---

## 14. シーンAPI

## 14.1 GET /projects/{project_id}/scenes

### 目的

作品のシーン一覧を取得する。

### Query

* `chapter_id`
* `include_choices`
* `include_versions`

### Response

```json
{
  "data": [
    {
      "id": 301,
      "chapter_id": 11,
      "title": "塔へ向かう夜",
      "summary": "ノアが塔へ案内する",
      "sort_order": 1,
      "is_fixed": false
    }
  ]
}
```

---

## 14.2 POST /projects/{project_id}/scenes

### 目的

シーンを新規作成する。

### Request

```json
{
  "chapter_id": 11,
  "title": "塔へ向かう夜",
  "summary": "ノアが塔へ案内する",
  "sort_order": 1
}
```

---

## 14.3 GET /scenes/{scene_id}

### 目的

シーン詳細を取得する。

### Response

```json
{
  "data": {
    "id": 301,
    "project_id": 10,
    "chapter_id": 11,
    "title": "塔へ向かう夜",
    "summary": "ノアが塔へ案内する",
    "narration_text": "夜風の中、ノアが振り返った。",
    "dialogues": [
      {
        "speaker": "ノア",
        "text": "こっちだよ。中央演算塔はもうすぐ。"
      }
    ],
    "scene_state": {
      "location": "高層歩廊",
      "time_of_day": "night",
      "mood": "mysterious"
    },
    "image_prompt_text": "Noa on a futuristic skywalk at night"
  }
}
```

---

## 14.4 PATCH /scenes/{scene_id}

### 目的

シーン本文や状態を部分更新する。

### Request

```json
{
  "narration_text": "夜風の中、ノアが静かに微笑んだ。",
  "dialogues": [
    {
      "speaker": "ノア",
      "text": "こっちだよ。中央演算塔はもうすぐ。"
    }
  ]
}
```

---

## 14.5 POST /scenes/{scene_id}/generate

### 目的

シーン本文、会話、選択肢を AI で生成する。

### Request

```json
{
  "mode": "next_scene",
  "instruction": "ノアらしい穏やかな口調で、少し神秘的に",
  "choice_count": 3,
  "regenerate": false
}
```

### Response

```json
{
  "data": {
    "job_id": 2001,
    "status": "queued"
  }
}
```

### 備考

* 実際の生成結果は job 完了後に scene_version または generated_candidate へ保存

---

## 14.6 POST /scenes/{scene_id}/extract-state

### 目的

シーン本文から画像生成用状態JSONを抽出する。

### Request

```json
{
  "source": "current_scene"
}
```

### Response

```json
{
  "data": {
    "job_id": 2002,
    "status": "queued"
  }
}
```

---

## 14.7 POST /scenes/{scene_id}/fix

### 目的

シーンを固定して再生成対象から外す。

## 14.8 POST /scenes/{scene_id}/unfix

### 目的

シーン固定を解除する。

---

## 15. シーン選択肢API

## 15.1 GET /scenes/{scene_id}/choices

### 目的

シーンの選択肢一覧を取得する。

## 15.2 POST /scenes/{scene_id}/choices

### 目的

選択肢を追加する。

### Request

```json
{
  "choice_text": "中央演算塔について聞く",
  "next_scene_id": 302,
  "sort_order": 1
}
```

## 15.3 PATCH /scene-choices/{choice_id}

### 目的

選択肢を更新する。

## 15.4 DELETE /scene-choices/{choice_id}

### 目的

選択肢を削除する。

---

## 16. シーン履歴API

## 16.1 GET /scenes/{scene_id}/versions

### 目的

シーンの履歴一覧を取得する。

### Response

```json
{
  "data": [
    {
      "id": 9001,
      "version_no": 1,
      "source_type": "ai",
      "is_adopted": true,
      "created_at": "2026-04-18T16:20:00+09:00"
    },
    {
      "id": 9002,
      "version_no": 2,
      "source_type": "manual",
      "is_adopted": false,
      "created_at": "2026-04-18T16:25:00+09:00"
    }
  ]
}
```

## 16.2 POST /scenes/{scene_id}/versions/{version_id}/adopt

### 目的

シーン履歴を採用版にする。

### Response

```json
{
  "data": {
    "scene_id": 301,
    "active_version_id": 9002
  }
}
```

---

## 17. 画像生成API

## 17.1 GET /scenes/{scene_id}/images

### 目的

シーンに紐づく画像一覧を取得する。

### Response

```json
{
  "data": [
    {
      "id": 7001,
      "asset_id": 8001,
      "quality": "low",
      "size": "1024x1024",
      "is_selected": true,
      "image_url": "/api/v1/assets/8001"
    }
  ]
}
```

---

## 17.2 POST /scenes/{scene_id}/images/generate

### 目的

シーン用画像を生成する。

### Request

```json
{
  "quality": "low",
  "size": "1024x1024",
  "target": "scene_full",
  "use_character_base": true,
  "instruction": "ノアの表情を少し柔らかくする"
}
```

### Response

```json
{
  "data": {
    "job_id": 3001,
    "status": "queued"
  }
}
```

### 備考

* target は `scene_full`, `background_only`, `character_only` など
* `use_character_base=true` の場合、登場キャラクターの `base_asset_id` を参照画像として渡す
* 参照画像がある場合、OpenAI 画像編集系APIの reference image / image-to-image 相当のフローを使う

---

## 17.3 POST /scene-images/{scene_image_id}/select

### 目的

採用画像として選択する。

## 17.4 POST /scene-images/{scene_image_id}/regenerate

### 目的

既存条件をベースに再生成する。

---

## 18. アセットAPI

## 18.1 POST /assets/upload

### 目的

参照画像やサムネイルをアップロードする。

### Request

* multipart/form-data
* file
* asset_type
* project_id (optional)

### Response

```json
{
  "data": {
    "id": 55,
    "file_name": "noa_base.png",
    "asset_type": "reference_image"
  }
}
```

### 備考

* `asset_type=reference_image` を指定すると、キャラクター基準画像として利用できる

---

## 18.2 GET /assets/{asset_id}

### 目的

アセットメタ情報を取得するか、画像を返却する。

### 備考

* 実装方式によってはメタ情報取得APIとダウンロードAPIを分けてもよい

---

## 19. ジョブAPI

## 19.1 GET /jobs/{job_id}

### 目的

ジョブ状態を取得する。

### Response

```json
{
  "data": {
    "id": 3001,
    "job_type": "image_generation",
    "status": "success",
    "target_type": "scene",
    "target_id": 301,
    "started_at": "2026-04-18T16:30:00+09:00",
    "finished_at": "2026-04-18T16:30:12+09:00",
    "result": {
      "scene_image_id": 7001,
      "asset_id": 8001
    }
  }
}
```

## 19.2 GET /projects/{project_id}/jobs

### 目的

作品単位のジョブ履歴を取得する。

---

## 20. プレビューAPI

## 20.1 GET /projects/{project_id}/preview

### 目的

プレビュー開始用データを取得する。

### Response

```json
{
  "data": {
    "project": {
      "id": 10,
      "title": "ラプラスシティ探索記"
    },
    "first_scene_id": 301
  }
}
```

## 20.2 GET /projects/{project_id}/preview/scenes/{scene_id}

### 目的

プレビュー画面で1シーン分の表示情報を取得する。

### Response

```json
{
  "data": {
    "scene_id": 301,
    "title": "塔へ向かう夜",
    "image": {
      "asset_id": 8001,
      "url": "/api/v1/assets/8001"
    },
    "narration_text": "夜風の中、ノアが静かに微笑んだ。",
    "dialogues": [
      {
        "speaker": "ノア",
        "text": "こっちだよ。中央演算塔はもうすぐ。"
      }
    ],
    "choices": [
      {
        "id": 5001,
        "text": "中央演算塔について聞く"
      }
    ]
  }
}
```

---

## 21. エクスポートAPI

## 21.1 POST /projects/{project_id}/exports

### 目的

作品をエクスポートする。

### Request

```json
{
  "export_type": "json",
  "include_images": true
}
```

### Response

```json
{
  "data": {
    "job_id": 4001,
    "status": "queued"
  }
}
```

## 21.2 GET /projects/{project_id}/exports

### 目的

作品のエクスポート履歴を取得する。

## 21.3 GET /exports/{export_job_id}

### 目的

エクスポートジョブ詳細を取得する。

---

## 22. 非同期ジョブ設計

## 22.1 非同期対象

以下はジョブ化する。

* ストーリー骨子生成
* シーン生成
* 状態JSON抽出
* 画像生成
* エクスポート

## 22.2 ジョブ状態

* `queued`
* `running`
* `success`
* `failed`

## 22.3 フロントでの扱い

* 生成開始時に job_id を受け取る
* 数秒おきに `/jobs/{job_id}` をポーリングする
* 成功時に対象リソースを再取得する

---

## 23. バリデーション方針

### 作品作成

* title 必須
* genre 必須
* project_type 必須

### キャラクター作成

* name 必須
* project_id 必須

### シーン作成

* project_id 必須
* chapter_id 必須
* sort_order 必須

### 画像生成

* quality は low / medium / high のいずれか
* size は `1024x1024`, `1024x1536`, `1536x1024` のいずれかを許可

---

## 24. セキュリティ方針

### 24.1 認可チェック

* すべての project 配下リソースで所有者確認を行う

### 24.2 ファイルアップロード

* MIME type を検証する
* 想定外拡張子を拒否する
* サイズ制限を設ける

### 24.3 ログ

* 生成失敗や例外はサーバ側で記録する
* 機密情報は response_json にそのまま保存しない

---

## 25. MVPで優先実装するAPI

### 優先度A

* POST `/auth/register`
* POST `/auth/login`
* GET `/auth/me`
* GET `/projects`
* POST `/projects`
* GET `/projects/{project_id}`
* PATCH `/projects/{project_id}`
* GET `/projects/{project_id}/world`
* PUT `/projects/{project_id}/world`
* GET `/projects/{project_id}/characters`
* POST `/projects/{project_id}/characters`
* PATCH `/characters/{character_id}`
* PUT `/characters/{character_id}/image-rule`
* GET `/projects/{project_id}/chapters`
* POST `/projects/{project_id}/chapters`
* GET `/projects/{project_id}/scenes`
* POST `/projects/{project_id}/scenes`
* GET `/scenes/{scene_id}`
* PATCH `/scenes/{scene_id}`
* POST `/scenes/{scene_id}/generate`
* POST `/scenes/{scene_id}/extract-state`
* POST `/scenes/{scene_id}/images/generate`
* GET `/jobs/{job_id}`
* GET `/projects/{project_id}/preview/scenes/{scene_id}`
* POST `/assets/upload`

### 優先度B

* シーン履歴API
* エクスポートAPI
* 用語辞書API

---

## 26. まとめ

本API設計は、AIノベルゲームツクールの制作UIを支えるために、**作品編集系API** と **AI生成ジョブAPI** を分けて設計している。

特に重要なのは以下。

* シーン生成を同期レスポンスで返し切らず、ジョブ化すること
* シーン本文、状態抽出、画像生成を分離すること
* キャラクター固定ルールを独立APIで管理すること
* プレビューAPIでは「そのまま表示できる形」を返すこと

MVPではまず、作品、キャラクター、世界観、シーン、画像生成、ジョブ取得の主要APIを実装すれば、制作体験の中核は成立する。
