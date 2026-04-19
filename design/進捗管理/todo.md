# TODOリスト
最終更新: 2026-04-19（テキスト履歴強化 / story_memory 追加）

## 方針
- 設計書群 `design/API設計書.md` / `design/DB設計書.md` / `design/アーキテクチャ設計書.md` / `design/画面詳細設計.md` に沿って、実装中のダミー・仮実装・未接続箇所を順に埋める。
- 大きなファイルを一度に直しすぎず、1ファイルずつ確実に進める。
- 優先度は `Blueprint接続` → `生成フロー接続` → `テスト` → `確認・ドキュメント更新` とする。

---

## 0. 現在地
### 実装済み寄り
- Service の主要部は実装済み
  - `app/services/project_service.py`
  - `app/services/glossary_service.py`
  - `app/services/scene_choice_service.py`
  - `app/services/story_outline_service.py`
  - `app/services/usage_log_service.py`
  - `app/services/world_service.py`
  - `app/services/auth_service.py`
  - `app/services/generation_service.py`
- AI client の雛形は実装済み
  - `app/clients/image_ai_client.py`
  - `app/clients/text_ai_client.py`
- Blueprint で Service 接続済み（2026-04-19 時点）
  - `app/blueprints/projects/routes.py`
  - `app/blueprints/worlds/routes.py`
  - `app/blueprints/story_outline/routes.py`
  - `app/blueprints/glossary/routes.py`
  - `app/blueprints/auth/routes.py`
  - `app/blueprints/scenes/routes.py`
  - `app/blueprints/scene_versions/routes.py`
  - `app/blueprints/chapters/routes.py`
  - `app/blueprints/characters/routes.py`
  - `app/blueprints/scene_images/routes.py`
  - `app/blueprints/exports/routes.py`
  - `app/blueprints/jobs/routes.py`（progress は status からの簡易算出）
  - `app/blueprints/assets/routes.py`

### 未完了・未確認
- Flask アプリ全体の実起動確認、主要 API の通し確認は未完了
- `character_image_rule` 用の SQL は追加済みだが、DB へ適用したかは未確認
- `tests/` 配下の pytest 実行確認は未完了
- 画面設計との最終差分整理、README 反映は未完了

---

## 1. 最優先TODO: BlueprintをServiceへ接続する
### 1-1. Projects API
- [x] `app/blueprints/projects/routes.py`
  - [x] `ProjectService` を import して利用する
  - [x] `GET /projects` をダミーデータ返却から実データ返却に変える
  - [x] `POST /projects` を実作成処理に変える
  - [x] `GET /projects/<project_id>` を実取得処理に変える
  - [x] `PATCH /projects/<project_id>` を実更新処理に変える
  - [x] `DELETE /projects/<project_id>` を実削除処理に変える
  - [x] 404 / 400 のエラーハンドリングを統一する
  - [x] API設計書のレスポンス形式に合わせる

### 1-2. Worlds API
- [x] `app/blueprints/worlds/routes.py`
  - [x] `WorldService` を呼ぶようにする
  - [x] `GET /projects/<project_id>/world` を実取得に接続する
  - [x] `PUT /projects/<project_id>/world` を upsert 実装に接続する
  - [x] world 未存在時の 404 または空データ方針を再確認する
  - [x] API設計書の整合を合わせる

### 1-3. Story Outline API
- [x] `app/blueprints/story_outline/routes.py`
  - [x] `StoryOutlineService` を呼ぶようにする
  - [x] `GET /projects/<project_id>/story-outline` を実取得に接続する
  - [x] `PUT /projects/<project_id>/story-outline` を upsert に接続する
  - [x] `POST /projects/<project_id>/story-outline/generate` を generation job 起票に接続する
  - [x] 202 Accepted の返却形式をジョブ情報ベースに調整する

### 1-4. Glossary API
- [x] `app/blueprints/glossary/routes.py`
  - [x] `GlossaryService` を呼ぶようにする
  - [x] `GET /projects/<project_id>/glossary` を実データ返却にする
  - [x] `POST /projects/<project_id>/glossary` を実作成にする
  - [x] `PATCH /glossary/<term_id>` を実更新にする
  - [x] `DELETE /glossary/<term_id>` を実削除にする

### 1-5. Scenes / Scene Choices API
- [x] `app/blueprints/scenes/routes.py`
  - [x] `SceneService` を接続する
  - [x] `SceneChoiceService` を接続する
  - [x] `GET /projects/<project_id>/scenes` を一覧取得にする
  - [x] `POST /projects/<project_id>/scenes` を作成にする
  - [x] `GET /scenes/<scene_id>` を詳細取得にする
  - [x] `PATCH /scenes/<scene_id>` を更新にする
  - [x] `DELETE /scenes/<scene_id>` を削除にする
  - [x] `POST /scenes/<scene_id>/generate` を `GenerationService` 連携にする
  - [x] `POST /scenes/<scene_id>/extract-state` を `GenerationService` 連携にする
  - [x] `POST /scenes/<scene_id>/fix` / `unfix` を実処理にする
  - [x] `GET /scenes/<scene_id>/choices` を一覧取得にする
  - [x] `POST /scenes/<scene_id>/choices` を作成にする
  - [x] `PATCH /scene-choices/<choice_id>` を更新にする
  - [x] `DELETE /scene-choices/<choice_id>` を削除にする

### 1-6. Scene Versions API
- [x] `app/blueprints/scene_versions/routes.py`
  - [x] `SceneVersionService` を接続する
  - [x] `GET /scenes/<scene_id>/versions` を一覧取得にする
  - [x] `POST /scenes/<scene_id>/versions/<version_id>/adopt` を実適用処理にする

### 1-7. Auth API の実装
- [x] `app/blueprints/auth/routes.py`
  - [x] Blueprint直書きロジックを `AuthService` 利用へ寄せる
  - [x] login/logout/me の呼び出し先を実装する
  - [x] session と token の扱い方針を明記する
  - [x] 401 / 400 の返し方を API と揃える

---

## 2. 次点TODO: 未接続・ダミー Blueprint を個別に実装する
### 2-1. Chapters API
- [x] `app/blueprints/chapters/routes.py`
  - [x] 既存 service / repository の有無を確認する
  - [x] 一覧・作成・更新・削除を設計書に沿って実装する

### 2-2. Characters API
- [x] `app/blueprints/characters/routes.py`
  - [x] Character 系 service / repository / model を調整する
  - [x] 一覧・作成・更新・削除を実装する
  - [x] image rule API の呼び出しを実装する
  - [x] `GET /characters/<character_id>/image-rule` を実装する
  - [x] `PUT /characters/<character_id>/image-rule` を実装する
  - [x] `character_image_rule` 用の model / repository / service を追加する

### 2-3. Assets API
- [x] `app/blueprints/assets/routes.py`
  - [x] Asset 系 model / repository / service の有無を確認する
  - [x] 一覧・詳細・更新・削除を設計書準拠で実装する
  - [x] `POST /assets/upload` を追加する

### 2-4. Exports API
- [x] `app/blueprints/exports/routes.py`
  - [x] `ExportService` を接続する
  - [x] 一覧取得・詳細取得を実装する
  - [ ] エクスポートジョブ起票 API が必要なら追加実装する

### 2-5. Jobs API
- [x] `app/blueprints/jobs/routes.py`
  - [x] GenerationJob / ExportJob の取得元を整理する
  - [x] `GET /jobs/<job_id>` を実ジョブ取得に変える
  - [x] status / progress / error_message を返せるようにする
  - [x] 共通取得用として `app/services/job_query_service.py` を追加する

### 2-6. Scene Images API
- [x] `app/blueprints/scene_images/routes.py`
  - [x] 既存 `SceneImage` モデルに合わせて返却形式を揃える
  - [x] `GenerationService.enqueue_image_generation` と接続する
  - [x] generate / regenerate 系エンドポイントを実ジョブ起票へ寄せる

---

## 3. 生成フローを実用化させる
### 3-1. GenerationService の実運用接続
- [x] `app/services/generation_service.py`
  - [x] job_type ごとの分岐が設計どおりか確認する
  - [x] text generation の実処理を `TextAIClient` と接続する
  - [x] image generation の実処理を `ImageAIClient` と接続する
  - [x] state extraction の実処理を `TextAIClient.extract_state_json` と接続する
  - [x] usage log 記録の呼び出しを実装する
  - [x] scene version / generated candidate / asset / scene image 反映を基本実装する

### 3-2. Text AI Client 実運用確認
- [x] `app/clients/text_ai_client.py`
  - [x] 詳細設計書どおりのシグネチャと返却形式を確認する
  - [x] OpenAI API エラー時の例外設計を統一する
  - [x] タイムアウト / リトライ方針を決める
  - [x] usage 情報の返却形式を保持する
  - [x] JSON抽出失敗時は `parsed_json=None` で扱う
  - [x] 同章の直近シーンと story_memory を prompt に渡す下地を追加する

### 3-3. Image AI Client 実運用確認
- [x] `app/clients/image_ai_client.py`
  - [x] 詳細設計書どおりのレスポンス形式を確認する
  - [x] base64 / URL のどちらを扱うかを実装に反映する
  - [x] APIエラー / タイムアウト時の例外を統一する
  - [x] 画像保存処理と asset 連携を `GenerationService` 側で実装する

---

## 4. Prompt Builder を実装する
### 4-1. Scene Prompt Builder
- [x] `app/prompts/scene_prompt_builder.py`
  - [x] TODO を解消する
  - [x] project / world / story_outline / scene / glossary / character 情報を取り込めるよう設計する
  - [x] 生成AI向け最低限の出力誘導テンプレートを張る
  - [x] 状態抽出用と本文生成用で prompt を分ける方針を決める

### 4-2. Image Prompt Builder
- [x] `app/prompts/image_prompt_builder.py`
  - [x] TODO を解消する
  - [x] シーン本文・人物設計・画風指定から画像生成向け prompt を構成する
  - [x] 禁止語や style 指定を含める方針を決める

---

## 5. モデル・Repository・Service の抜け漏れ調査
### 5-1. 未接続リソースの調査
- [x] Chapters 関連の model / repository / service の有無を整理する
- [x] Characters 関連の model / repository / service の有無を整理する
- [x] Assets 関連の model / repository / service の有無を整理する
- [x] Jobs 横断 service が必要か確認する

### 5-2. レイヤ呼び出しの統一
- [x] Service で入力値整形する方針を全箇所で統一する
- [x] Repository は DB CRUD に集中させる方針を確認する
- [x] Blueprint のシリアライズ呼び出しを統一する
  - [x] 404 / 400 / 401 / 422 の返し方を統一する

### 5-3. テキスト文脈メモリ
- [x] `story_memory` テーブルを追加する
- [x] シーン更新時に `scene_digest` / `conversation_note` / `player_profile` を同期する
- [x] scene prompt に `recent_scenes` と `story_memories` を渡す

---

## 6. 認証・セッション周りを実装する
- [x] `app/services/auth_service.py`
  - [x] login / logout / me の処理を Blueprint と統一する
  - [x] token 返却ではなく session ベースで行く方針を明記する
  - [x] 認証ログや usage_log と連携する方針を実装する
  - [x] register の処理を追加する
- [x] `app/blueprints/auth/routes.py`
  - [x] 現在の session 実装を service 中心へ実装する
  - [x] `POST /auth/register` を追加する
- [x] `app/models/user.py`
  - [x] status / password_hash / display_name の利用方針を確認する
  - [x] `set_password` / `verify_password` / `is_active_user` を追加する

---

## 7. 画面詳細との差分を埋める
- [x] `design/画面仕様書.md` と現モデル差分を洗い出す
- [x] world の「世界観説明」「文明レベル設定」など、画面側の項目差分を確認する
  - [x] `GET /projects/<project_id>/world` に `ui_fields` を追加する
  - [x] `PUT /projects/<project_id>/world` で画面向け別名フィールドも受け付ける
  - [x] `GET /projects/<project_id>/world-context` を追加する
- [x] glossary / characters / assets の画面想定と API の差分を詰める
  - `assets` は metadata API として接続済み。ファイル添付導線との整合は別途確認
  - `characters image-rule` は API 実装済み。画面側項目との整合は別途確認
- [x] scene editor / image確認 / preview 向けの集約 API を追加する
  - [x] `GET /projects/<project_id>/overview`
  - [x] `GET /scenes/<scene_id>/editor-context`
  - [x] `GET /scenes/<scene_id>/image-context`
  - [x] `GET /scenes/<scene_id>/preview`

---

## 8. DB・起動確認・環境整備
- [x] SQLite / 開発DB のどちらを使うかを確認する
- [ ] 全テーブルが設計どおり存在するか確認する
- [x] 起動ユーザー作成手順を確認する
- [x] ローカル起動手順を README または設計書へ追記する
- [x] `/health` または主要 API の起動確認に使える簡易確認を用意する
- [x] `character_image_rule` 用の手動適用 SQL を `migrations/20260419_add_character_image_rule.sql` として追加する
- [ ] 上記 SQL を実DBへ適用したか確認する

---

## 9. 画面実装TODO（Bootstrap 5.3）
- [x] Bootstrap 5.3 を前提にした画面基盤を追加する
  - [x] `templates/` と `static/` の基本構成を追加する
  - [x] 共通レイアウト、ヘッダー、サイドメニュー、トースト、モーダルを作る
  - [x] API 呼び出し用の共通 JavaScript を用意する
- [x] ログイン画面を作成する
  - [x] メールアドレス / パスワード入力
  - [x] ログイン実行
  - [x] エラー表示
  - [x] ユーザー登録画面への導線
- [x] ユーザー登録画面を作成する
  - [x] 表示名 / メールアドレス / パスワード入力
  - [x] ユーザー登録実行
  - [x] ログイン画面への戻り導線
- [x] ダッシュボード画面を作成する
  - [x] 最近の作品一覧
  - [x] 新規作成導線
  - [x] 更新通知 / 利用状況のプレースホルダ表示
- [x] 作品一覧画面を作成する
  - [x] 一覧表示
  - [x] 検索 / 絞り込み
  - [x] 新規作成 / 編集トップへの導線
- [x] 作品新規作成画面を作成する
  - [x] タイトル、ジャンル、あらすじ、想定プレイ時間、制作方式入力
  - [x] バリデーション表示
- [x] 作品編集トップ画面を作成する
  - [x] `GET /projects/<project_id>/overview` を使った概要表示
  - [x] 各編集画面への導線
- [x] 世界観設定画面を作成する
  - [x] `GET /projects/<project_id>/world-context` を使った初期表示
  - [x] world 更新フォーム
  - [x] 用語辞典への導線
- [x] キャラクター一覧画面を作成する
  - [x] 一覧、検索、追加導線
  - [x] 基準画像サムネイル表示
- [x] キャラクター編集画面を作成する
  - [x] 基本情報 / 性格 / 外見 / 画像固定ルールフォーム
  - [x] 画像テスト生成導線
  - [x] 基準画像アップロードと `base_asset_id` 連携
- [x] ストーリー骨子設定画面を作成する
  - [x] 骨子表示 / 更新
  - [x] AI生成導線
- [x] シーン一覧・編集画面を作成する
  - [x] 左ツリー、中央エディタ、右補助情報パネル
  - [x] `GET /scenes/<scene_id>/editor-context` を使った編集 UI
  - [x] generate / extract-state / fix / image generate の操作ボタン
- [x] シーン生成結果確認画面を作成する
  - [x] 候補比較 UI
  - [x] 採用 / 再生成導線
- [x] 画像生成確認画面を作成する
  - [x] `GET /scenes/<scene_id>/image-context` を使った確認 UI
  - [x] 再生成 / 採用 / 不採用導線
- [x] プレビュー画面を作成する
  - [x] `GET /scenes/<scene_id>/preview` を使ったノベルゲーム風 UI
  - [x] 次へ / 選択肢 / ログ表示
- [x] エクスポート画面を作成する
  - [x] 出力形式選択
  - [x] 実行 / 結果表示
- [x] 設定画面を作成する
  - [x] 利用モデル、画像品質、サイズ、自動保存などの設定 UI

---

## 10. GPT / OpenAI API 実接続TODO
- [ ] `OPENAI_API_KEY` を使った実接続確認を行う
- [ ] `TextAIClient` の chat completions 呼び出しを実環境で確認する
  - [ ] テキスト生成成功レスポンス確認
  - [ ] JSON応答確認
  - [ ] 失敗時メッセージ確認
- [ ] `ImageAIClient` の images API 呼び出しを実環境で確認する
  - [ ] 画像生成成功レスポンス確認
  - [ ] base64 保存確認
  - [ ] revised prompt / エラー応答確認
  - [x] 参照画像あり時に `images/edits` を使う実装へ拡張
  - [ ] `base_asset_id` を参照画像として渡す実環境確認
- [ ] GPT モデル名と実使用 API の整合を確認する
  - [ ] `TEXT_AI_MODEL`
  - [ ] `IMAGE_AI_MODEL`
- [ ] API キー未設定時の UI / エラーメッセージ導線を整える
- [ ] OpenAI 利用設定を README に追記する

---

## 11. テストTODO
### 9-1. 単体テスト
- [ ] ProjectService
- [ ] GlossaryService
- [ ] SceneService
- [ ] SceneChoiceService
- [ ] StoryOutlineService
- [ ] WorldService
- [ ] UsageLogService
- [x] AuthService
- [ ] TextAIClient（モック前提）
- [ ] ImageAIClient（モック前提）

### 9-2. APIテスト
- [x] auth login / logout / me
- [ ] project CRUD
- [ ] world get / put
- [ ] story-outline get / put / generate
- [ ] glossary CRUD
- [ ] scene CRUD
- [ ] scene choice CRUD
- [x] scene generation / state extraction
- [ ] scene image generation
- [ ] ending condition CRUD
- [x] jobs get

### 9-3. テストケース整理
- [ ] Flask 用の HTTP テストケースを追加する
- [ ] `defaults.base_url` を使う YAML を整理する
- [ ] login → project作成 → world更新 → story-outline更新 → scene作成 の Happy Path を通す
- [x] pytest 用の基礎 fixture (`tests/conftest.py`) を追加する
- [x] `tests/test_auth_service.py` を追加する
- [x] `tests/test_scenes_api.py` を追加する
- [x] `tests/test_auth_api.py` を追加する
- [x] `tests/test_jobs_api.py` を追加する
- [ ] `pytest` を実際に導入して実行確認する

---

## 12. ドキュメント更新
- [ ] 詳細設計書と実装差分を随時更新する
- [ ] 実装したファイルをこの TODO から消し込む
- [x] API設計書との差分が出たら設計書へ反映する
- [ ] 新規ルールやファイル追加を運用メモへ簡潔に追記する

---

## 13. 実装順の目安
下から順に進めると、破綻しにくい。
1. [x] `app/blueprints/projects/routes.py`
2. [x] `app/blueprints/worlds/routes.py`
3. [x] `app/blueprints/story_outline/routes.py`
4. [x] `app/blueprints/glossary/routes.py`
5. [x] `app/blueprints/scenes/routes.py`
6. [x] `app/blueprints/scene_versions/routes.py`
7. [x] `app/blueprints/auth/routes.py`
8. [x] `app/prompts/scene_prompt_builder.py`
9. [x] `app/prompts/image_prompt_builder.py`
10. [x] `app/blueprints/jobs/routes.py`
11. [x] `app/blueprints/exports/routes.py`
12. [x] `app/blueprints/chapters/routes.py`
13. [x] `app/blueprints/characters/routes.py`
14. [x] `app/blueprints/assets/routes.py`
15. [x] `app/blueprints/scene_images/routes.py`
16. [ ] API疎通テスト
17. [ ] 単体テスト
18. [ ] 起動確認

---

## 14. 実装完了の定義
以下を満たしたら「実装完了」とみなす。
- [ ] 主要 Blueprint がダミー応答ではなく Service / Repository / Model に接続されている
- [x] Prompt Builder の TODO が解消されている
- [x] Auth / Text AI / Image AI の呼び出しが実装側で接続済み
- [ ] Bootstrap 5.3 ベースの主要画面が操作可能である
- [ ] OpenAI API の実接続確認が完了している
- [ ] 主要 API の Happy Path テストが通る
- [ ] 設計書と実装の差分が説明・反映されている
- [ ] ローカルで一連の基本操作が確認できる
