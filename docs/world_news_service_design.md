# ワールドニュース / 噂サービス 設計

## 目的

チャット、ストーリー、おでかけ、施設情報を横断して、世界がユーザーの外側でも動いているように見せる。
「街の噂」「施設ニュース」「キャラ同士の関係ログ」を同じサービスで扱い、クリックすると関連キャラ・施設・おでかけへつながる導線にする。

## 初期スコープ

- プロジェクト単位でニュース/噂を保存する。
- 関連キャラクター、関連施設、発生元、重要度、本文、導線URLを持つ。
- 画面名は「ワールドニュース」。
- 手動でAI生成できる。
- おでかけ完了時に1件自動生成する。
- 一般ユーザーも閲覧できる。
- 管理者/プロジェクトユーザーは手動生成できる。

## データ

- `world_news_item`
  - `project_id`
  - `created_by_user_id`
  - `related_character_id`
  - `related_location_id`
  - `news_type`: `location_news`, `character_sighting`, `relationship`, `outing_afterglow`, `event_hint`
  - `title`
  - `body`
  - `summary`
  - `importance`: 1〜5
  - `source_type`: `manual_ai`, `outing_completed`, `fallback`
  - `source_ref_type`
  - `source_ref_id`
  - `return_url`
  - `status`: `published`, `draft`, `archived`
  - `metadata_json`

## API

- `GET /api/v1/projects/<project_id>/world-news`
  - 公開中のニュース/噂一覧。
- `POST /api/v1/projects/<project_id>/world-news/generate`
  - 最近のキャラ/施設/おでかけ状況からAIで噂を生成。
- `POST /api/v1/projects/<project_id>/world-news`
  - 手動作成。

## 次フェーズ

- チャット/ストーリーのプロンプトへ最近の噂を注入する。
- Feed投稿の材料にする。
- キャラ同士の関係値を別テーブル化する。
- ニュースクリックからおでかけを直接開始する。
