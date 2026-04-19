# AIノベルゲームツクール DB設計書（SQLite3版）

## 1. 目的

本書は、AIノベルゲームツクールにおける SQLite3 前提のデータベース設計を定義する。

本システムでは、作品、キャラクター、世界観、章、シーン、選択肢、画像生成履歴、生成ジョブ、エクスポート履歴などを扱う。SQLite3 を採用することで、**ローカル開発しやすく、単体アプリや小規模運用に向いた構成** を実現する。

---

## 2. 前提

### 2.1 採用DB

* SQLite3

### 2.2 SQLite3 を採用する理由

* ローカル開発が容易
* 単体アプリや試作段階で扱いやすい
* サーバ不要で導入コストが低い
* データを1ファイルで持てるためバックアップしやすい

### 2.3 注意点

* 高い同時書き込み性能は期待しない
* 大規模マルチユーザー運用には不向き
* JSON 型はないため、柔軟構造は TEXT に JSON文字列として保存する
* 厳密な enum 型はないため、CHECK 制約またはアプリ側で制御する

---

## 3. 設計方針

### 3.1 基本方針

* 正規化を基本とする
* 柔軟データは TEXT(JSON文字列) で保持する
* 作品単位での参照を重視し、 `project_id` を主要な検索軸とする
* 生成AIの再生成や履歴比較に耐えられるよう、バージョン管理テーブルを設ける
* 画像ファイル本体はファイルシステムまたはオブジェクトストレージに置き、DBにはパスやメタ情報のみ保持する

### 3.2 命名規則

* テーブル名は単数形
* 主キーは `id`
* 外部キーは `<entity>_id`
* 作成日時: `created_at`
* 更新日時: `updated_at`
* 論理削除日時: `deleted_at`

### 3.3 ID方針

SQLite3 では以下のどちらかで運用する。

* MVP: INTEGER PRIMARY KEY AUTOINCREMENT
* 将来移行を見据える場合: TEXT(UUID文字列)

本設計書では、**SQLite3 で扱いやすい INTEGER PRIMARY KEY AUTOINCREMENT** を基本とする。

---

## 4. ER概要

主要エンティティは以下。

* user
* project
* world
* glossary_term
* character
* character_image_rule
* story_outline
* chapter
* ending_condition
* scene
* scene_choice
* scene_version
* scene_image
* generated_candidate
* story_memory
* asset
* generation_job
* export_job
* usage_log

主な関係:

* user は複数の project を持つ
* project は 1 つの world を持つ
* project は複数の character を持つ
* project は 1 つの story_outline を持つ
* project は複数の chapter を持つ
* chapter は複数の scene を持つ
* scene は複数の choice を持つ
* scene は複数の version を持つ
* scene は複数の image を持つ
* project は複数の story_memory を持つ
* asset は画像・出力ファイル・参照画像などを管理する

---

## 5. テーブル定義

## 5.1 user

### 目的

利用者情報を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* email: TEXT NOT NULL UNIQUE
* display_name: TEXT NOT NULL
* password_hash: TEXT NULL
* auth_provider: TEXT NOT NULL DEFAULT 'local'
* status: TEXT NOT NULL DEFAULT 'active'
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL
* deleted_at: TEXT NULL

### 備考

* 日時は ISO 8601 文字列で保持
* MVPでは単一ユーザー運用なら簡略化も可能

---

## 5.2 project

### 目的

ノベルゲーム制作単位のプロジェクトを保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* owner_user_id: INTEGER NOT NULL
* world_id: INTEGER NULL
* title: TEXT NOT NULL
* slug: TEXT NULL
* genre: TEXT NOT NULL
* summary: TEXT NULL
* play_time_minutes: INTEGER NULL
* project_type: TEXT NOT NULL
* status: TEXT NOT NULL DEFAULT 'draft'
* thumbnail_asset_id: INTEGER NULL
* settings_json: TEXT NULL
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL
* deleted_at: TEXT NULL

### 外部キー

* owner_user_id -> user.id
* world_id -> world.id
* thumbnail_asset_id -> asset.id

### 制約例

* project_type IN ('linear', 'branching', 'exploration')
* status IN ('draft', 'editing', 'completed', 'archived')

### インデックス

* INDEX(owner_user_id)
* INDEX(world_id)
* INDEX(status)

---

## 5.3 world

### 目的

作品の世界観設定を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL UNIQUE
* name: TEXT NOT NULL
* era_description: TEXT NULL
* technology_level: TEXT NULL
* social_structure: TEXT NULL
* tone: TEXT NULL
* overview: TEXT NULL
* rules_json: TEXT NULL
* forbidden_json: TEXT NULL
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL

### 外部キー

* project_id -> project.id

### 備考

* 1 project に対して 1 world を基本とする

---

## 5.4 glossary_term

### 目的

固有名詞辞書・用語集を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* world_id: INTEGER NOT NULL
* term: TEXT NOT NULL
* reading: TEXT NULL
* description: TEXT NULL
* category: TEXT NULL
* sort_order: INTEGER NOT NULL DEFAULT 0
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL

### 外部キー

* world_id -> world.id

### インデックス

* INDEX(world_id)
* INDEX(term)

---

## 5.5 character

### 目的

作品に登場するキャラクター情報を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL
* name: TEXT NOT NULL
* role: TEXT NULL
* age_impression: TEXT NULL
* first_person: TEXT NULL
* second_person: TEXT NULL
* personality: TEXT NULL
* speech_style: TEXT NULL
* speech_sample: TEXT NULL
* ng_rules: TEXT NULL
* appearance_summary: TEXT NULL
* base_asset_id: INTEGER NULL
* is_guide: INTEGER NOT NULL DEFAULT 0
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL
* deleted_at: TEXT NULL

### 外部キー

* project_id -> project.id
* base_asset_id -> asset.id

### インデックス

* INDEX(project_id)
* INDEX(name)

### 備考

* is_guide は案内役キャラ判定用。0/1 の整数で管理
* `base_asset_id` はキャラクターの基準画像を指し、画像生成時の reference image として利用する

---

## 5.6 character_image_rule

### 目的

キャラクター画像生成時の固定ルールを保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* character_id: INTEGER NOT NULL UNIQUE
* hair_rule: TEXT NULL
* face_rule: TEXT NULL
* ear_rule: TEXT NULL
* accessory_rule: TEXT NULL
* outfit_rule: TEXT NULL
* style_rule: TEXT NULL
* negative_rule: TEXT NULL
* default_quality: TEXT NOT NULL DEFAULT 'low'
* default_size: TEXT NOT NULL DEFAULT '1024x1024'
* prompt_prefix: TEXT NULL
* prompt_suffix: TEXT NULL
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL

### 外部キー

* character_id -> character.id

### 備考

* ノアなら ear_rule に `human ears` を入れる
* default_quality は low / medium / high を想定
* 参照画像を使う場合は `prompt_prefix` や `prompt_suffix` で image-to-image 前提の補足を入れる

---

## 5.7 story_outline

### 目的

作品全体の骨子を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL UNIQUE
* premise: TEXT NULL
* protagonist_position: TEXT NULL
* main_goal: TEXT NULL
* branching_policy: TEXT NULL
* ending_policy: TEXT NULL
* outline_text: TEXT NULL
* outline_json: TEXT NULL
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL

### 外部キー

* project_id -> project.id

---

## 5.8 chapter

### 目的

章情報を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL
* chapter_no: INTEGER NOT NULL
* title: TEXT NOT NULL
* summary: TEXT NULL
* objective: TEXT NULL
* sort_order: INTEGER NOT NULL
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL

### 外部キー

* project_id -> project.id

### インデックス

* INDEX(project_id)
* UNIQUE(project_id, chapter_no)

---

## 5.9 ending_condition

### 目的

エンディング条件を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL
* ending_type: TEXT NOT NULL
* name: TEXT NOT NULL
* condition_text: TEXT NULL
* condition_json: TEXT NULL
* priority: INTEGER NOT NULL DEFAULT 0
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL

### 外部キー

* project_id -> project.id

### 備考

* ending_type は true / normal / bad / secret などを想定

---

## 5.10 scene

### 目的

シーンの現行版情報を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL
* chapter_id: INTEGER NOT NULL
* parent_scene_id: INTEGER NULL
* scene_key: TEXT NULL
* title: TEXT NULL
* summary: TEXT NULL
* narration_text: TEXT NULL
* dialogue_json: TEXT NULL
* scene_state_json: TEXT NULL
* image_prompt_text: TEXT NULL
* active_version_id: INTEGER NULL
* sort_order: INTEGER NOT NULL
* is_fixed: INTEGER NOT NULL DEFAULT 0
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL
* deleted_at: TEXT NULL

### 外部キー

* project_id -> project.id
* chapter_id -> chapter.id
* parent_scene_id -> scene.id
* active_version_id -> scene_version.id

### インデックス

* INDEX(project_id)
* INDEX(chapter_id)
* INDEX(parent_scene_id)
* INDEX(sort_order)

### 備考

* dialogue_json はセリフ配列をJSON文字列で保持
* is_fixed は再生成禁止や保護対象シーン判定

---

## 5.11 scene_choice

### 目的

シーンごとの選択肢を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* scene_id: INTEGER NOT NULL
* choice_text: TEXT NOT NULL
* next_scene_id: INTEGER NULL
* condition_json: TEXT NULL
* result_summary: TEXT NULL
* sort_order: INTEGER NOT NULL
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL

### 外部キー

* scene_id -> scene.id
* next_scene_id -> scene.id

### インデックス

* INDEX(scene_id)
* INDEX(next_scene_id)

---

## 5.12 scene_version

### 目的

シーンの生成履歴・編集履歴を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* scene_id: INTEGER NOT NULL
* version_no: INTEGER NOT NULL
* source_type: TEXT NOT NULL
* generated_by: TEXT NULL
* narration_text: TEXT NULL
* dialogue_json: TEXT NULL
* choice_json: TEXT NULL
* scene_state_json: TEXT NULL
* image_prompt_text: TEXT NULL
* note_text: TEXT NULL
* is_adopted: INTEGER NOT NULL DEFAULT 0
* created_at: TEXT NOT NULL

### 外部キー

* scene_id -> scene.id

### 備考

* source_type は ai / manual / mixed など
* choice_json は version時点の選択肢スナップショット

### インデックス

* INDEX(scene_id)
* UNIQUE(scene_id, version_no)

---

## 5.13 scene_image

### 目的

シーンに紐づく生成画像を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* scene_id: INTEGER NOT NULL
* scene_version_id: INTEGER NULL
* asset_id: INTEGER NOT NULL
* image_type: TEXT NOT NULL
* generation_job_id: INTEGER NULL
* prompt_text: TEXT NULL
* state_json: TEXT NULL
* quality: TEXT NOT NULL
* size: TEXT NOT NULL
* is_selected: INTEGER NOT NULL DEFAULT 0
* created_at: TEXT NOT NULL

### 外部キー

* scene_id -> scene.id
* scene_version_id -> scene_version.id
* asset_id -> asset.id
* generation_job_id -> generation_job.id

### 備考

* image_type は background / character / scene_full など

### インデックス

* INDEX(scene_id)
* INDEX(scene_version_id)
* INDEX(is_selected)

---

## 5.14 generated_candidate

### 目的

シーン本文や画像の候補比較結果を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL
* target_type: TEXT NOT NULL
* target_id: INTEGER NOT NULL
* candidate_type: TEXT NOT NULL
* content_text: TEXT NULL
* content_json: TEXT NULL
* score: REAL NULL
* tags_json: TEXT NULL
* is_selected: INTEGER NOT NULL DEFAULT 0
* created_at: TEXT NOT NULL

### 備考

* target_type は scene / image_generation など
* candidate_type は narrative / choice / image_prompt など

### インデックス

* INDEX(project_id)
* INDEX(target_type, target_id)

---

## 5.15 asset

### 目的

画像・参照画像・出力ファイルなどのメタ情報を管理する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NULL
* asset_type: TEXT NOT NULL
* file_name: TEXT NOT NULL
* file_path: TEXT NOT NULL
* mime_type: TEXT NULL
* file_size: INTEGER NULL
* width: INTEGER NULL
* height: INTEGER NULL
* checksum: TEXT NULL
* metadata_json: TEXT NULL
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL
* deleted_at: TEXT NULL

### 備考

* asset_type は reference_image / generated_image / export_file / thumbnail など
* `reference_image` はキャラクター基準画像や構図参照画像を想定する

### インデックス

* INDEX(project_id)
* INDEX(asset_type)
* INDEX(checksum)

---

## 5.16 story_memory

### 目的

プレイヤー名、重要会話メモ、シーン要約など、長い文脈を要約して保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL
* chapter_id: INTEGER NULL
* scene_id: INTEGER NULL
* memory_type: TEXT NOT NULL
* memory_key: TEXT NOT NULL
* content_text: TEXT NOT NULL
* detail_json: TEXT NULL
* importance: INTEGER NOT NULL DEFAULT 0
* created_at: TEXT NOT NULL
* updated_at: TEXT NOT NULL

### 外部キー

* project_id -> project.id
* chapter_id -> chapter.id
* scene_id -> scene.id

### 備考

* `player_profile`, `conversation_note`, `scene_digest` などを格納する
* 生成プロンプトには同章の直近シーンとあわせて投入する

### インデックス

* INDEX(project_id)
* INDEX(chapter_id)
* INDEX(memory_type, memory_key)

---

## 5.17 generation_job

### 目的

AI生成処理の実行履歴を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL
* job_type: TEXT NOT NULL
* target_type: TEXT NOT NULL
* target_id: INTEGER NULL
* model_name: TEXT NULL
* request_json: TEXT NULL
* response_json: TEXT NULL
* status: TEXT NOT NULL
* started_at: TEXT NULL
* finished_at: TEXT NULL
* error_message: TEXT NULL
* created_at: TEXT NOT NULL

### 備考

* job_type は text_generation / image_generation / state_extraction
* status は queued / running / success / failed

### インデックス

* INDEX(project_id)
* INDEX(job_type)
* INDEX(status)

---

## 5.17 export_job

### 目的

エクスポート履歴を保持する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* project_id: INTEGER NOT NULL
* export_type: TEXT NOT NULL
* asset_id: INTEGER NULL
* status: TEXT NOT NULL
* options_json: TEXT NULL
* started_at: TEXT NULL
* finished_at: TEXT NULL
* error_message: TEXT NULL
* created_at: TEXT NOT NULL

### 外部キー

* project_id -> project.id
* asset_id -> asset.id

### インデックス

* INDEX(project_id)
* INDEX(status)

---

## 5.18 usage_log

### 目的

利用量や生成回数の集計に利用する。

### カラム

* id: INTEGER PRIMARY KEY AUTOINCREMENT
* user_id: INTEGER NOT NULL
* project_id: INTEGER NULL
* action_type: TEXT NOT NULL
* quantity: INTEGER NOT NULL DEFAULT 1
* unit: TEXT NULL
* detail_json: TEXT NULL
* created_at: TEXT NOT NULL

### 備考

* 画像生成回数、テキスト生成回数、推定コストなどを記録する

### インデックス

* INDEX(user_id)
* INDEX(project_id)
* INDEX(action_type)
* INDEX(created_at)

---

## 6. CREATE TABLE 例

以下は MVP 向けの代表テーブルDDL例。

```sql
CREATE TABLE user (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  password_hash TEXT,
  auth_provider TEXT NOT NULL DEFAULT 'local',
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE TABLE project (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL,
  world_id INTEGER,
  title TEXT NOT NULL,
  slug TEXT,
  genre TEXT NOT NULL,
  summary TEXT,
  play_time_minutes INTEGER,
  project_type TEXT NOT NULL CHECK(project_type IN ('linear','branching','exploration')),
  status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','editing','completed','archived')),
  thumbnail_asset_id INTEGER,
  settings_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY (owner_user_id) REFERENCES user(id),
  FOREIGN KEY (world_id) REFERENCES world(id),
  FOREIGN KEY (thumbnail_asset_id) REFERENCES asset(id)
);

CREATE TABLE character (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  name TEXT NOT NULL,
  role TEXT,
  age_impression TEXT,
  first_person TEXT,
  second_person TEXT,
  personality TEXT,
  speech_style TEXT,
  speech_sample TEXT,
  ng_rules TEXT,
  appearance_summary TEXT,
  base_asset_id INTEGER,
  is_guide INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY (project_id) REFERENCES project(id),
  FOREIGN KEY (base_asset_id) REFERENCES asset(id)
);

CREATE TABLE scene (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  chapter_id INTEGER NOT NULL,
  parent_scene_id INTEGER,
  scene_key TEXT,
  title TEXT,
  summary TEXT,
  narration_text TEXT,
  dialogue_json TEXT,
  scene_state_json TEXT,
  image_prompt_text TEXT,
  active_version_id INTEGER,
  sort_order INTEGER NOT NULL,
  is_fixed INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY (project_id) REFERENCES project(id),
  FOREIGN KEY (chapter_id) REFERENCES chapter(id),
  FOREIGN KEY (parent_scene_id) REFERENCES scene(id),
  FOREIGN KEY (active_version_id) REFERENCES scene_version(id)
);

CREATE TABLE scene_choice (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  scene_id INTEGER NOT NULL,
  choice_text TEXT NOT NULL,
  next_scene_id INTEGER,
  condition_json TEXT,
  result_summary TEXT,
  sort_order INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (scene_id) REFERENCES scene(id),
  FOREIGN KEY (next_scene_id) REFERENCES scene(id)
);
```

---

## 7. インデックス設計方針

### 7.1 基本方針

SQLite3 は過剰なインデックスで書き込みが重くなるため、最小限にする。

### 7.2 優先インデックス

* project.owner_user_id
* character.project_id
* chapter.project_id
* scene.project_id
* scene.chapter_id
* scene_choice.scene_id
* scene_version.scene_id
* scene_image.scene_id
* generation_job.project_id
* usage_log.user_id, created_at

### 7.3 補足

* JSON文字列内部の検索は不得意なので、頻出条件は専用カラム化する
* 例: status, project_type, is_fixed など

---

## 8. トランザクション方針

### 8.1 用途

以下はトランザクションでまとめる。

* シーン作成 + 選択肢作成
* シーン採用 + active_version_id 更新
* 画像生成結果保存 + asset 登録 + scene_image 登録

### 8.2 注意

SQLite3 は書き込みロックが強いため、長いトランザクションは避ける。

---

## 9. JSON保存方針

SQLite3 では JSON 型がないため、以下は TEXT(JSON文字列)で保持する。

* project.settings_json
* world.rules_json
* world.forbidden_json
* story_outline.outline_json
* scene.dialogue_json
* scene.scene_state_json
* scene_version.choice_json
* scene_version.scene_state_json
* scene_image.state_json
* generation_job.request_json
* generation_job.response_json

### 方針

* 保存前にアプリ側でJSON妥当性を検証する
* 頻繁に検索する属性は JSON に埋めず通常カラムに出す

---

## 10. 論理削除方針

### 対象

* user
* project
* character
* scene
* asset

### 方針

* `deleted_at` が NULL なら有効
* 完全削除は管理用機能またはメンテナンス処理で実施

---

## 11. MVPで最低限必要なテーブル

MVPで最初に作るべきテーブルは以下。

* user
* project
* world
* character
* character_image_rule
* chapter
* scene
* scene_choice
* scene_version
* asset
* scene_image
* generation_job

これで以下が成立する。

* 作品作成
* キャラクター登録
* 世界観登録
* シーン生成
* 選択肢分岐
* 画像生成履歴保存
* プレビュー用データ取得

---

## 12. 将来拡張

### 12.1 将来的に追加しうるテーブル

* template
* project_template_link
* collaboration_invite
* comment
* bgm_setting
* publish_job
* analytics_snapshot

### 12.2 PostgreSQL移行時の検討

* INTEGER 主キーから UUID への変更
* JSONB 利用
* 部分インデックス導入
* 複数ユーザー同時編集への対応

---

## 13. まとめ

本設計は SQLite3 を前提として、**MVPを早く作るための軽量なRDB設計** を意識している。

重要なポイントは以下。

* 柔軟データは TEXT(JSON文字列) で持つ
* 頻出検索条件は通常カラムに分離する
* シーンと画像は履歴管理を前提にする
* 画像本体はDBに入れず、assetでメタ管理する
* SQLite3 の特性上、書き込み競合と過剰インデックスを避ける

初期段階ではこの設計で十分実用的であり、後に PostgreSQL 等へ移行しやすい形にもなっている。
