# DB設計書差分（ライブ会話モード）

## 1. 目的

本書は、既存の [DB設計書.md](./DB設計書.md) をベースに、ライブ会話モードを実現するために必要な差分を整理する。

ここでは以下を明確にする。

- 追加するテーブル
- 流用する既存テーブル
- 縮小または依存を弱める既存テーブル
- MVP での最小構成

---

## 2. 差分方針

ライブ会話モードでは、`chapter / scene / story_outline` 主体の物語制作構造から、`chat_session / chat_message / session_state` 主体の会話ランタイム構造へ重心を移す。

ただし、既存資産を活用するため、以下の方針を取る。

- `project` は引き続き親コンテナとして使う
- `character` と `asset` は流用する
- 画像保存は当面 `scene_image` の仕組み流用も許容する
- 新しい中心データだけを追加する

---

## 3. 追加テーブル

## 3.1 chat_session

### 目的

会話単位のセッションを保持する。

### カラム案

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `project_id`: INTEGER NOT NULL
- `title`: TEXT NULL
- `session_type`: TEXT NOT NULL DEFAULT 'live_chat'
- `status`: TEXT NOT NULL DEFAULT 'active'
- `active_image_id`: INTEGER NULL
- `player_name`: TEXT NULL
- `settings_json`: TEXT NULL
- `created_at`: TEXT NOT NULL
- `updated_at`: TEXT NOT NULL
- `deleted_at`: TEXT NULL

### 外部キー

- `project_id -> project.id`
- `active_image_id -> asset.id` または `session_image.id`

### 補足

- `player_name` は session 単位で上書きできるように持つ
- project 単位の主人公名がある場合でも session 側で上書き可

---

## 3.2 chat_message

### 目的

ユーザー発話、キャラクター発話、システムメッセージを時系列で保持する。

### カラム案

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `session_id`: INTEGER NOT NULL
- `sender_type`: TEXT NOT NULL
- `speaker_name`: TEXT NULL
- `message_text`: TEXT NOT NULL
- `order_no`: INTEGER NOT NULL
- `message_role`: TEXT NULL
- `state_snapshot_json`: TEXT NULL
- `created_at`: TEXT NOT NULL

### 外部キー

- `session_id -> chat_session.id`

### 制約例

- `sender_type IN ('user', 'character', 'system')`

### 補足

- `state_snapshot_json` は、その発話時点の状態を簡易保存するために使う

---

## 3.3 session_state

### 目的

その時点の背景、表情、ポーズ、カメラ、ムードなど、ライブ会話中の現在状態を保持する。

### カラム案

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `session_id`: INTEGER NOT NULL UNIQUE
- `state_json`: TEXT NOT NULL
- `narration_note`: TEXT NULL
- `visual_prompt_text`: TEXT NULL
- `updated_at`: TEXT NOT NULL

### 外部キー

- `session_id -> chat_session.id`

### 補足

- `narration_note` は内部用描写メモ
- `visual_prompt_text` は直近画像生成に使った整形済みプロンプト

---

## 3.4 session_character

### 目的

会話セッションに参加するキャラクターを管理する。

### カラム案

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `session_id`: INTEGER NOT NULL
- `character_id`: INTEGER NOT NULL
- `role_type`: TEXT NOT NULL DEFAULT 'main'
- `sort_order`: INTEGER NOT NULL DEFAULT 0
- `created_at`: TEXT NOT NULL

### 外部キー

- `session_id -> chat_session.id`
- `character_id -> character.id`

### 補足

- MVP では 1〜2人程度の参加を想定

---

## 3.5 session_image（新設案）

### 目的

ライブ会話セッション中に生成・アップロード・採用された画像候補を管理する。

### カラム案

- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `session_id`: INTEGER NOT NULL
- `asset_id`: INTEGER NOT NULL
- `image_type`: TEXT NOT NULL
- `prompt_text`: TEXT NULL
- `state_json`: TEXT NULL
- `quality`: TEXT NULL
- `size`: TEXT NULL
- `is_selected`: INTEGER NOT NULL DEFAULT 0
- `created_at`: TEXT NOT NULL

### 外部キー

- `session_id -> chat_session.id`
- `asset_id -> asset.id`

### 補足

- 当面は既存 `scene_image` の流用も可能
- 将来的には `session_image` へ独立した方が意味が明確

---

## 4. 既存テーブルの流用

## 4.1 project

### 扱い

流用する。

### 理由

- 作品単位の世界観、キャラ、設定の親として有効
- 完全に捨てる必要はない

---

## 4.2 character

### 扱い

そのまま流用する。

### 理由

- 名前、口調、性格、外見、基準画像の軸として重要

---

## 4.3 asset

### 扱い

そのまま流用する。

### 理由

- 基準画像
- 背景画像
- 生成画像
- 手動アップロード画像

を一元管理できる

---

## 4.4 character_image_rule

### 扱い

流用する。

### 理由

- 基準画像ベースの見た目安定化に利用できる

---

## 4.5 story_memory

### 扱い

部分流用する。

### 理由

- プレイヤー名
- 重要な関係性
- 口約束
- 目的

などの継続文脈を保持するために有効

### 補足

- session 単位の文脈へ寄せるなら、将来的に `session_memory` へ分離も検討

---

## 5. 既存テーブルの位置づけ変更

## 5.1 story_outline

### 扱い

依存を弱める。

### 理由

- ライブ会話モードの主導線では骨子を必須にしない
- project 単位の世界観補助情報としては残してよい

---

## 5.2 chapter

### 扱い

ライブ会話モードでは非必須。

### 理由

- 章構成がなくても会話体験は成立する

---

## 5.3 scene / scene_choice / scene_version

### 扱い

ライブ会話モードの中心から外す。

### 理由

- 会話の即時性を重視するため、従来のシーン編集前提を外す

### 補足

- 当面は画像候補保存や一部履歴の流用先として残してよい

---

## 6. MVPの最小DB構成

ライブ会話モードだけを成立させる最小構成は以下。

- `project`
- `character`
- `asset`
- `character_image_rule`
- `chat_session`
- `chat_message`
- `session_state`
- `session_character`
- `session_image` または既存 `scene_image`

---

## 7. 推奨インデックス

### chat_session

- `INDEX(project_id)`
- `INDEX(status)`
- `INDEX(updated_at)`

### chat_message

- `INDEX(session_id, order_no)`
- `INDEX(session_id, created_at)`

### session_state

- `UNIQUE(session_id)`

### session_character

- `INDEX(session_id)`
- `INDEX(character_id)`

### session_image

- `INDEX(session_id)`
- `INDEX(is_selected)`

---

## 8. 移行案

## 8.1 段階移行

1. 既存DBは維持
2. 新規テーブルを追加
3. 新ルート `/live-chat` 系を追加
4. MVP を運用
5. 必要に応じて旧 `scene` 中心フローを縮小

## 8.2 データ移行の考え方

- 既存 `character` はそのまま使う
- 既存 `asset` はそのまま使う
- 既存 `story_memory` は必要なら session 開始時に参照する
- 旧 `scene` からの直接移行は MVP では不要

---

## 9. 未決事項

- [ ] `session_image` を新設するか、当面 `scene_image` を流用するか
- [ ] `player_name` を `chat_session` に持つか `project` / `story_outline` に持つか
- [ ] `story_memory` を流用するか `session_memory` を新設するか
- [ ] 1 session に何人まで参加させるか
- [ ] 背景画像を asset として明示管理するか、生成専用にするか

---

## 10. 推奨初期結論

まずは以下で始めるのが安全。

- `chat_session`
- `chat_message`
- `session_state`
- `session_character`
- 画像は既存 `asset + scene_image` を暫定流用

この構成なら、既存コードを流用しつつ、ライブ会話モードのMVPを比較的短期間で立ち上げやすい。
