# BlueprintをServiceへ接続する 詳細設計

最終更新: 2026-04-19

## 1. 目的

本設計は、現在ダミー応答のまま残っている `app/blueprints/*/routes.py` を、既存 Service 層へ順次接続し、`design/API設計書.md` に沿った実 API として動作させるための詳細設計を定義する。

本ドキュメントは、以下の TODO を具体化するものである。

- `design/進捗管理/todo.md`
  - 「## 1. 最優先TODO: BlueprintをServiceへ接続する」

---

## 2. 調査対象と現状

### 2.1 確認した現状ソース

#### ダミー応答の Blueprint
- `app/blueprints/projects/routes.py`
- `app/blueprints/worlds/routes.py`
- `app/blueprints/story_outline/routes.py`
- `app/blueprints/glossary/routes.py`
- `app/blueprints/scenes/routes.py`
- `app/blueprints/scene_versions/routes.py`
- `app/blueprints/chapters/routes.py`
- `app/blueprints/characters/routes.py`
- `app/blueprints/exports/routes.py`
- `app/blueprints/jobs/routes.py`
- `app/blueprints/assets/routes.py`
- `app/blueprints/auth/routes.py`

#### 接続先候補の Service
- `app/services/project_service.py`
- `app/services/world_service.py`
- `app/services/story_outline_service.py`
- `app/services/glossary_service.py`
- `app/services/scene_service.py`
- `app/services/scene_choice_service.py`
- `app/services/scene_version_service.py`
- `app/services/chapter_service.py`
- `app/services/character_service.py`
- `app/services/export_service.py`
- `app/services/auth_service.py`
- `app/services/generation_service.py`

#### 参照した設計書
- `design/API設計書.md`
- `design/進捗管理/todo.md`

### 2.2 現状の問題

現状の Blueprint は以下の状態である。

- `jsonify({"data": ...})` の固定値を返しているだけ
- request payload をそのまま `received` として返しているだけ
- Service を import していないものが多い
- エラーハンドリングが Blueprint ごとに未統一
- 認証 Blueprint は Service を通さず Model を直接操作している

このため、Service 層の実装が進んでいても、HTTP API としては未完成である。

---

## 3. 設計方針

### 3.1 基本方針

Blueprint 接続では以下の責務分担に統一する。

- **Blueprint**
  - HTTP 入出力を担当
  - request の取得
  - query/path/body の受け取り
  - Service 呼び出し
  - モデル/DTO の JSON 変換
  - HTTP ステータス決定
  - 例外から API エラー形式への変換

- **Service**
  - 入力検証
  - ユースケース制御
  - Repository / Model / 外部 Client 呼び出し

- **Repository**
  - DB CRUD

### 3.2 共通レスポンス形式

`design/API設計書.md` に合わせ、以下を共通ルールとする。

#### 成功
```json
{
  "data": {},
  "meta": {}
}
```

#### エラー
```json
{
  "error": {
    "code": "validation_error",
    "message": "title is required",
    "details": {}
  }
}
```

### 3.3 例外と HTTP ステータスの対応

Blueprint では Service 例外を以下へ写像する。

| 例外/状態 | HTTP | code | 備考 |
| --- | ---: | --- | --- |
| `ValueError` | 400 | `validation_error` | 入力不正 |
| `PermissionError` | 401 | `unauthorized` | 認証失敗 |
| `None` / `False` による未存在 | 404 | `not_found` | get/update/delete 失敗 |
| slug重複など競合 | 409 | `conflict` | `slug_already_exists` など |
| 想定外例外 | 500 | `internal_server_error` | 初期段階では共通文言 |

### 3.4 実装順序

Knowledge の指示どおり、**複数ファイルを同時に直さず、1ファイルずつ順番に**進める。

推奨順序:

1. `app/blueprints/projects/routes.py`
2. `app/blueprints/worlds/routes.py`
3. `app/blueprints/story_outline/routes.py`
4. `app/blueprints/glossary/routes.py`
5. `app/blueprints/scenes/routes.py`
6. `app/blueprints/scene_versions/routes.py`
7. `app/blueprints/auth/routes.py`
8. `app/blueprints/chapters/routes.py`
9. `app/blueprints/characters/routes.py`
10. `app/blueprints/exports/routes.py`
11. `app/blueprints/jobs/routes.py`
12. `app/blueprints/assets/routes.py`

---

## 4. Blueprint 共通実装ルール

### 4.1 共通 helper を Blueprint 内に置く

各 `routes.py` には最低限、以下の helper を持たせる。

#### `success_response(data, meta=None, status=200)`
```python
return jsonify({"data": data, "meta": meta or {}}), status
```

#### `error_response(code, message, status, details=None)`
```python
return jsonify({
    "error": {
        "code": code,
        "message": message,
        "details": details or {},
    }
}), status
```

### 4.2 シリアライズ関数を明示する

Service は ORM モデルを返すことがあるため、Blueprint 側でシリアライズ関数を持つ。

例:
- `_serialize_project(project)`
- `_serialize_world(world)`
- `_serialize_story_outline(outline)`
- `_serialize_glossary_term(term)`
- `_serialize_scene(scene)`
- `_serialize_scene_choice(choice)`
- `_serialize_scene_version(version)`
- `_serialize_chapter(chapter)`
- `_serialize_character(character)`
- `_serialize_export_job(job)`
- `_serialize_generation_job(job)`

### 4.3 `meta` の方針

- 単体取得: `meta={}`
- 一覧取得: 最低限 `meta` に親 ID を入れる
- ページング未実装一覧: `page/per_page/total` は暫定で入れず、現状は親 ID ベースに留めてもよい
- ただし `projects` 一覧は API設計書に近づけるため、将来的にページング拡張を見越した構造にする

### 4.4 request body の取得

すべての POST/PUT/PATCH は原則以下で受ける。

```python
payload = request.get_json(silent=True) or {}
```

ただし body 必須 API では空 dict をそのまま Service に渡し、`ValueError` を Service 側で発生させる。

---

## 5. ルート別詳細設計

## 5.1 Projects Blueprint

### 対象
- `app/blueprints/projects/routes.py`

### 現状
固定レスポンスのみ。

### 接続先 Service
- `ProjectService`

### 追加 import
```python
from ...services.project_service import ProjectService
```

### インスタンス化
```python
project_service = ProjectService()
```

### 必要な serialize
```python
def _serialize_project(project):
    return {
        "id": project.id,
        "owner_user_id": project.owner_user_id,
        "title": project.title,
        "slug": project.slug,
        "genre": project.genre,
        "concept": project.concept,
        "synopsis": project.synopsis,
        "status": project.status,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }
```

### ルート設計

#### GET `/projects`
- 認証済み user を仮に session から取得
- `owner_user_id = session.get("user_id")`
- 未ログインなら 401
- `service.list_projects(owner_user_id)` を呼ぶ
- `data` は project 配列
- `meta` は最低限 `{}` でもよいが、将来ページング拡張を見据えて構造を固定する

#### POST `/projects`
- 未ログインなら 401
- `payload` を取得
- `service.create_project(owner_user_id, payload)`
- `ValueError("slug_already_exists")` は 409 `conflict`
- 成功時 201

#### GET `/projects/<project_id>`
- `service.get_project(project_id)`
- `None` なら 404

#### PATCH `/projects/<project_id>`
- `payload` を取得
- `service.update_project(project_id, payload)`
- `None` なら 404
- `slug_already_exists` は 409

#### DELETE `/projects/<project_id>`
- `service.delete_project(project_id)`
- `False` なら 404
- 成功時は `{ "id": project_id, "deleted": true }`

### 留意点
- 認可は本来 project owner チェックが必要だが、現段階では service に owner 縛りが薄い
- 初期接続では session の user_id を取得し、create/list にのみ反映
- get/update/delete の owner チェックは別 TODO として残す

---

## 5.2 Worlds Blueprint

### 対象
- `app/blueprints/worlds/routes.py`

### 接続先 Service
- `WorldService`

### serialize
```python
def _serialize_world(world):
    return {
        "id": world.id,
        "project_id": world.project_id,
        "name": world.name,
        "era_description": world.era_description,
        "technology_level": world.technology_level,
        "social_structure": world.social_structure,
        "tone": world.tone,
        "overview": world.overview,
        "rules_json": world.rules_json,
        "forbidden_json": world.forbidden_json,
    }
```

### GET `/projects/<project_id>/world`
- `service.get_world(project_id)`
- `None` なら 404 `not_found`
- 成功時 200

### PUT `/projects/<project_id>/world`
- `payload` 取得
- `service.upsert_world(project_id, payload)`
- `ValueError` は 400
- 成功時 200

### 留意点
- 設計書上 `world` は project ごとに 1 件
- `PUT` でも service 実装は partial upsert 的に動くため、その前提で許容する

---

## 5.3 Story Outline Blueprint

### 対象
- `app/blueprints/story_outline/routes.py`

### 接続先 Service
- `StoryOutlineService`

### serialize
```python
def _serialize_story_outline(outline):
    return {
        "id": outline.id,
        "project_id": outline.project_id,
        "premise": outline.premise,
        "protagonist_position": outline.protagonist_position,
        "main_goal": outline.main_goal,
        "branching_policy": outline.branching_policy,
        "ending_policy": outline.ending_policy,
        "outline_text": outline.outline_text,
        "outline_json": outline.outline_json,
    }
```

```python
def _serialize_generation_job(job):
    return {
        "id": job.id,
        "project_id": job.project_id,
        "job_type": job.job_type,
        "target_type": job.target_type,
        "status": job.status,
        "model_name": job.model_name,
        "request_json": job.request_json,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
```

### GET `/projects/<project_id>/story-outline`
- `service.get_outline(project_id)`
- `None` なら 404

### PUT `/projects/<project_id>/story-outline`
- `service.upsert_outline(project_id, payload)`
- 400 on `ValueError`
- 成功時 200

### POST `/projects/<project_id>/story-outline/generate`
- `service.generate_outline(project_id, payload)`
- 生成ジョブを返す
- HTTP 202

### 返却例
```json
{
  "data": {
    "id": 10,
    "project_id": 1,
    "job_type": "story_outline_generation",
    "target_type": "story_outline",
    "status": "queued"
  },
  "meta": {}
}
```

---

## 5.4 Glossary Blueprint

### 対象
- `app/blueprints/glossary/routes.py`

### 接続先 Service
- `GlossaryService`

### serialize
```python
def _serialize_glossary_term(term):
    return {
        "id": term.id,
        "project_id": term.project_id,
        "world_id": term.world_id,
        "term": term.term,
        "category": term.category,
        "description": term.description,
        "aliases_json": term.aliases_json,
    }
```

### GET `/projects/<project_id>/glossary`
- query の `category` があれば service に渡す
- `service.list_terms(project_id, category=category)`

### POST `/projects/<project_id>/glossary`
- `service.create_term(project_id, payload)`
- `ValueError("world_not_found")` は 400 でよいが、将来は 404 化を検討
- 成功時 201

### PATCH `/glossary/<term_id>`
- `service.update_term(term_id, payload)`
- `None` なら 404

### DELETE `/glossary/<term_id>`
- `service.delete_term(term_id)`
- `False` なら 404

---

## 5.5 Scenes Blueprint

### 対象
- `app/blueprints/scenes/routes.py`

### 接続先 Service
- `SceneService`
- `SceneChoiceService`
- 将来的に `GenerationService`

### 現状評価
- Scene CRUD と Choice CRUD が同一ファイルに同居
- `generate` / `extract-state` / `fix` / `unfix` はまだ Service 側実装ギャップがある

### 接続段階を分ける

#### 第1段階
以下を先に接続する。
- GET `/projects/<project_id>/scenes`
- POST `/projects/<project_id>/scenes`
- GET `/scenes/<scene_id>`
- PATCH `/scenes/<scene_id>`
- GET `/scenes/<scene_id>/choices`
- POST `/scenes/<scene_id>/choices`
- PATCH `/scene-choices/<choice_id>`
- DELETE `/scene-choices/<choice_id>`

#### 第2段階
以下は追加調査後に接続する。
- DELETE `/scenes/<scene_id>`
- POST `/scenes/<scene_id>/generate`
- POST `/scenes/<scene_id>/extract-state`
- POST `/scenes/<scene_id>/fix`
- POST `/scenes/<scene_id>/unfix`

### 理由
- `SceneService` 現状には `delete_scene` / `fix` / `unfix` / `generate` / `extract_state` が無い
- 先に CRUD 接続だけ進めるのが安全

### serialize
```python
def _serialize_scene(scene):
    return {
        "id": scene.id,
        "project_id": scene.project_id,
        "chapter_id": scene.chapter_id,
        "title": scene.title,
        "summary": scene.summary,
        "scene_text": scene.scene_text,
        "state_json": scene.state_json,
        "is_fixed": scene.is_fixed,
        "sort_order": scene.sort_order,
    }
```

```python
def _serialize_scene_choice(choice):
    return {
        "id": choice.id,
        "scene_id": choice.scene_id,
        "choice_text": choice.choice_text,
        "next_scene_id": choice.next_scene_id,
        "condition_json": choice.condition_json,
        "result_summary": choice.result_summary,
        "sort_order": choice.sort_order,
    }
```

### 第1段階ルート設計

#### GET `/projects/<project_id>/scenes`
- `scene_service.list_scenes(project_id)`

#### POST `/projects/<project_id>/scenes`
- `scene_service.create_scene(project_id, payload)`
- `chapter_id` 欠如は 400

#### GET `/scenes/<scene_id>`
- `scene_service.get_scene(scene_id)`
- `None` なら 404

#### PATCH `/scenes/<scene_id>`
- `scene_service.update_scene(scene_id, payload)`
- `None` なら 404

#### GET `/scenes/<scene_id>/choices`
- `choice_service.list_choices(scene_id)`

#### POST `/scenes/<scene_id>/choices`
- `choice_service.create_choice(scene_id, payload)`
- 201

#### PATCH `/scene-choices/<choice_id>`
- `choice_service.update_choice(choice_id, payload)`
- `None` なら 404

#### DELETE `/scene-choices/<choice_id>`
- `choice_service.delete_choice(choice_id)`
- `False` なら 404

### 第2段階の設計メモ
- DELETE scene は `SceneService` へメソッド追加後に接続
- generate / extract-state は `GenerationService` と `TextAIClient` の責務整理後
- fix / unfix は Scene model / repository / service に専用更新メソッド追加後

---

## 5.6 Scene Versions Blueprint

### 対象
- `app/blueprints/scene_versions/routes.py`

### 接続先 Service
- `SceneVersionService`

### serialize
```python
def _serialize_scene_version(version):
    return {
        "id": version.id,
        "scene_id": version.scene_id,
        "version_no": version.version_no,
        "scene_text": version.scene_text,
        "state_json": version.state_json,
        "candidate_id": version.candidate_id,
        "adopted_at": version.adopted_at.isoformat() if version.adopted_at else None,
    }
```

### GET `/scenes/<scene_id>/versions`
- `service.list_versions(scene_id)` を返す

### POST `/scenes/<scene_id>/versions/<version_id>/adopt`
- `service.adopt_version(scene_id, version_id)`
- 失敗時は 404

---

## 5.7 Auth Blueprint

### 対象
- `app/blueprints/auth/routes.py`

### 現状
- Blueprint で `User.query` と `check_password_hash` を直接扱っている
- Service 層 `AuthService` があるのに未使用

### 接続先 Service
- `AuthService`

### 方針
セッション管理は Blueprint に残し、認証判定は Service に寄せる。

### 役割分担
- `AuthService.login(email, password)`
  - 資格情報検証
  - user 情報と token 返却
- Blueprint
  - `session["user_id"] = user["id"]`
  - response の HTTP 化

### ルート設計

#### POST `/auth/login`
- `payload` 取得
- `auth_service.login(email, password)`
- `ValueError` → 400
- `PermissionError` → 401
- 成功時 session に user_id 格納
- `data` には `token` と `user`

#### POST `/auth/logout`
- session clear
- `auth_service.logout(session_user_id)` を呼んでもよい
- 200

#### GET `/auth/me`
- session の user_id を取得
- `auth_service.get_current_user(user_id)`
- `None` なら 401
- 成功時 `user`

### 留意点
- API設計書は Bearer Token 前提だが、現実装は session ベース
- 当面は **session を正としつつ token も返す暫定運用** とする
- token 永続化/失効は別タスク

---

## 5.8 Chapters Blueprint

### 対象
- `app/blueprints/chapters/routes.py`

### 接続先 Service
- `ChapterService`

### serialize
```python
def _serialize_chapter(chapter):
    return {
        "id": chapter.id,
        "project_id": chapter.project_id,
        "title": chapter.title,
        "summary": chapter.summary,
        "sort_order": chapter.sort_order,
    }
```

### ルート設計
- GET `/projects/<project_id>/chapters` → `list_chapters`
- POST `/projects/<project_id>/chapters` → `create_chapter`, 201
- PATCH `/chapters/<chapter_id>` → `update_chapter`, `None` なら 404
- DELETE `/chapters/<chapter_id>` → `delete_chapter`, `False` なら 404

### 留意点
- Service 側バリデーションが薄い可能性があるため、初回接続時は 400/500 の境界に注意

---

## 5.9 Characters Blueprint

### 対象
- `app/blueprints/characters/routes.py`

### 接続先 Service
- `CharacterService`

### serialize
```python
def _serialize_character(character):
    return {
        "id": character.id,
        "project_id": character.project_id,
        "name": character.name,
        "role": character.role,
        "personality": character.personality,
        "appearance": character.appearance,
        "speech_style": character.speech_style,
        "background": character.background,
        "image_rule_json": character.image_rule_json,
    }
```

### 第1段階接続
- GET `/projects/<project_id>/characters`
- POST `/projects/<project_id>/characters`
- GET `/characters/<character_id>`
- PATCH `/characters/<character_id>`
- DELETE `/characters/<character_id>`

### 第2段階
- GET `/characters/<character_id>/image-rule`
- PUT `/characters/<character_id>/image-rule`

### 理由
- `CharacterService` 現状に image rule 専用メソッドが無い
- 第1段階は CRUD のみ接続

### image-rule 暫定方針
- 既存 model に `image_rule_json` があれば、それをキャラクター取得/更新経由で処理する形へ寄せる
- 専用 API は別設計後に実装

---

## 5.10 Exports Blueprint

### 対象
- `app/blueprints/exports/routes.py`

### 接続先 Service
- `ExportService`

### serialize
```python
def _serialize_export_job(job):
    return {
        "id": job.id,
        "project_id": job.project_id,
        "export_type": job.export_type,
        "asset_id": job.asset_id,
        "options_json": job.options_json,
        "status": job.status,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error_message": job.error_message,
    }
```

### GET `/projects/<project_id>/exports`
- `service.list_exports(project_id)`

### POST `/projects/<project_id>/exports`
- `service.create_export(project_id, payload)`
- 生成ではなく export job 作成なので 202

### GET `/exports/<export_job_id>`
- `service.get_export(export_job_id)`
- `None` なら 404

---

## 5.11 Jobs Blueprint

### 対象
- `app/blueprints/jobs/routes.py`

### 現状
- 専用 service が無い

### 方針
この段階では **新規 service を先に作る必要がある**。

候補:
- `JobQueryService`
  - `get_job(job_id)`
  - GenerationJob / ExportJob の両方を探索する

### 現段階の設計判断
- jobs Blueprint は最優先接続対象からは外し、後続フェーズで対応
- 本詳細設計では「新規 service 作成が必要」と定義する

### 想定返却
```json
{
  "data": {
    "id": 123,
    "job_type": "scene_generation",
    "status": "queued",
    "progress": 0,
    "error_message": null
  },
  "meta": {}
}
```

---

## 5.12 Assets Blueprint

### 対象
- `app/blueprints/assets/routes.py`

### 現状
- API設計書と routes の内容にずれがある
  - API設計書: `POST /assets/upload`, `GET /assets/{asset_id}`
  - 現 routes: project 配下 list/create, asset update/delete まで存在

### 接続先候補
- `AssetService`

### 設計判断
- まずは **API設計書との差分整理が必要**
- 直ちに接続実装するより、先に「正式な assets API の形」を確定すべき

### 本設計での扱い
- Assets Blueprint は最優先から外す
- `design/API設計書.md` と routes の差分調整を先行タスクとする

---

## 6. 共通エラーハンドリング詳細

### 6.1 衝突エラー
以下のような文字列メッセージは 409 にマップする。

- `slug_already_exists`

返却例:
```json
{
  "error": {
    "code": "conflict",
    "message": "slug_already_exists",
    "details": {}
  }
}
```

### 6.2 404 判定
以下を 404 とする。

- `service.get_xxx(...) is None`
- `service.update_xxx(...) is None`
- `service.delete_xxx(...) is False`

### 6.3 401 判定
以下を 401 とする。

- 未ログイン
- `PermissionError("invalid credentials")`
- `auth_service.get_current_user(...) is None`

---

## 7. 実装フェーズ分割

## フェーズ1: すぐ接続できる CRUD を接続
対象:
- projects
- worlds
- story_outline
- glossary
- scene_versions
- chapters
- exports
- auth

条件:
- 対応 Service が既にあり、最低限の public method が存在する

## フェーズ2: CRUD だが不足メソッドがあるものを補完後接続
対象:
- scenes
- characters

必要追加:
- `SceneService.delete_scene`
- `SceneService.fix_scene` / `unfix_scene`
- 生成関連との接続面整理
- Character image-rule 専用責務の整理

## フェーズ3: 追加 service/設計調整が必要
対象:
- jobs
- assets

必要追加:
- Job 参照用 service
- Asset API の正式仕様確定

---

## 8. 実装時のチェックリスト

各 Blueprint を実装するときは毎回以下を確認する。

1. Service import がある
2. `payload = request.get_json(silent=True) or {}` が適切に使われている
3. `success_response` / `error_response` がある
4. ORM モデルの serialize 関数がある
5. `ValueError` を 400 に変換している
6. `slug_already_exists` など競合を 409 に変換している
7. `None` / `False` を 404 に変換している
8. 認証が必要な API は session を確認している
9. API設計書どおりの HTTP ステータスになっている
10. `data` / `meta` の形式が揃っている

---

## 9. 実装完了条件

「BlueprintをServiceへ接続する」が完了したとみなす条件は以下。

- `projects/routes.py` がダミー返却を卒業している
- `worlds/routes.py` が `WorldService` を呼ぶ
- `story_outline/routes.py` が `StoryOutlineService` を呼ぶ
- `glossary/routes.py` が `GlossaryService` を呼ぶ
- `scene_versions/routes.py` が `SceneVersionService` を呼ぶ
- `auth/routes.py` が `AuthService` を使う
- `chapters/routes.py` が `ChapterService` を呼ぶ
- `exports/routes.py` が `ExportService` を呼ぶ
- `scenes/routes.py` は少なくとも CRUD と choice CRUD の第1段階が接続される
- 各 Blueprint のエラーレスポンス形式が統一される

---

## 10. 補足: 今回の設計で未決事項として残すもの

以下は今回の Blueprint 接続とは切り分ける。

- Bearer Token 本実装
- project 所有者チェックの厳格化
- jobs API 用統合 JobService の追加
- assets API の正式仕様決定
- scene generate / extract-state の実ジョブ実行
- character image-rule 専用 API の確定
- projects 一覧のページング本実装

これらは接続後の次フェーズで対応する。
