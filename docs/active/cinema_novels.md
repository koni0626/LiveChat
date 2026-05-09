# シネマノベル正式仕様

更新日: 2026-05-09

## 位置づけ

シネマノベルは正式機能とする。

管理者とプロジェクトユーザーにとっては、制作機能であり、閲覧機能でもある。一般ユーザーにとっては閲覧機能であり、制作はできない。

ショートコミックもシネマノベルと同じ正式機能として扱う。現在実装されているシネマノベル/ショートコミック関連機能はすべてサポート対象とする。

## 権限

| ロール | 制作 | 閲覧 | 備考 |
| --- | --- | --- | --- |
| superuser | 可 | 可 | 全体管理、公開状態、出力、生成系を扱える。 |
| project_user | 可 | 可 | 自分が管理/参加できるプロジェクト内で制作できる。 |
| user | 不可 | 可 | 公開済み、かつ閲覧可能な作品のみ読める。 |

閲覧制御:

- 未公開作品は、制作権限を持つユーザーだけが閲覧できる。
- 一般ユーザーは公開済み作品のみ閲覧できる。
- mobile visible が無効な作品は、モバイル判定時に一般ユーザーへ表示しない。

制作制御:

- 一般ユーザーは、ノベル作成、生成、更新、削除、画像編集、出力、BGMアップロードなどの制作操作を行えない。
- 制作操作は、プロジェクト管理権限を持つユーザーに限定する。

## 対象機能

以下はすべて正式サポート対象とする。

### ノベル管理

- ノベル一覧
- ノベル詳細
- ノベル削除
- 公開状態更新
- mobile visible制御
- 読書進捗保存

関連:

- UI: `/projects/<project_id>/cinema-novels`
- UI: `/projects/<project_id>/cinema-novels/<novel_id>`
- API: `GET /api/v1/projects/<project_id>/cinema-novels`
- API: `GET /api/v1/cinema-novels/<novel_id>`
- API: `DELETE /api/v1/cinema-novels/<novel_id>`
- API: `PUT /api/v1/cinema-novels/<novel_id>/status`
- API: `PUT /api/v1/cinema-novels/<novel_id>/progress`

### 文章制作

- Markdownフォルダimport
- production premise生成
- production outline生成
- production outline保存
- production outline job
- production outlineからchapter作成
- chapter markdown更新
- chapter deepening draft
- chapter deepen
- chapter image plan生成

関連:

- API: `POST /api/v1/projects/<project_id>/cinema-novels/import-markdown-folder`
- API: `POST /api/v1/projects/<project_id>/cinema-novels/production-premise`
- API: `POST /api/v1/projects/<project_id>/cinema-novels/production-outline`
- API: `POST /api/v1/projects/<project_id>/cinema-novels/production-outline/save`
- API: `POST /api/v1/projects/<project_id>/cinema-novels/production-outline-jobs`
- API: `GET /api/v1/projects/<project_id>/cinema-novels/production-outline-jobs/<job_id>`
- API: `POST /api/v1/cinema-novels/<novel_id>/chapters/from-production-outline`
- API: `PUT /api/v1/cinema-novels/<novel_id>/chapters/<chapter_id>`
- API: `POST /api/v1/projects/<project_id>/cinema-novels/chapter-deepening-draft`
- API: `POST /api/v1/cinema-novels/<novel_id>/chapters/<chapter_id>/deepen`
- API: `POST /api/v1/cinema-novels/<novel_id>/chapters/<chapter_id>/image-plan`

### 画像制作

- title image生成
- chapter images生成
- 表示画像edit
- 表示画像upload
- 表示画像delete
- 画像履歴から選択

関連:

- API: `POST /api/v1/cinema-novels/<novel_id>/title-image`
- API: `POST /api/v1/cinema-novels/<novel_id>/chapters/<chapter_id>/images`
- API: `POST /api/v1/cinema-novels/<novel_id>/image-edit`
- API: `POST /api/v1/cinema-novels/<novel_id>/image-upload`
- API: `DELETE /api/v1/cinema-novels/<novel_id>/image`
- API: `PUT /api/v1/cinema-novels/<novel_id>/image-history`

### ショートコミック

ショートコミックは正式機能とする。シネマノベルの一形式として扱い、制作権限と閲覧権限もシネマノベルに準じる。

正式サポート対象:

- short comic job
- short comic novel作成
- comic scenes更新
- comic scenes再生成
- comic scenes mutate
- comic special image更新
- comic special image再生成
- comic short video export

関連:

- API: `POST /api/v1/projects/<project_id>/cinema-novels/short-comic-jobs`
- API: `GET /api/v1/projects/<project_id>/cinema-novels/short-comic-jobs/<job_id>`
- API: `PUT /api/v1/cinema-novels/<novel_id>/comic-scenes`
- API: `POST /api/v1/cinema-novels/<novel_id>/comic-scenes/regenerate`
- API: `POST /api/v1/cinema-novels/<novel_id>/comic-scenes/mutate`
- API: `PUT /api/v1/cinema-novels/<novel_id>/comic-special-image`
- API: `POST /api/v1/cinema-novels/<novel_id>/comic-special-image/regenerate`
- API: `GET /api/v1/cinema-novels/<novel_id>/comic-short-video`

## 出力

以下の出力は正式サポート対象とする。

- PowerPoint
- EPUB
- short video
- comic short video

関連:

- API: `GET /api/v1/cinema-novels/<novel_id>/powerpoint`
- API: `GET /api/v1/cinema-novels/<novel_id>/epub`
- API: `GET /api/v1/cinema-novels/<novel_id>/short-video`
- API: `GET /api/v1/cinema-novels/<novel_id>/comic-short-video`

## 作品補助情報

以下も正式サポート対象とする。

- BGM asset一覧
- BGM assetアップロード
- character review生成/一覧
- lore生成/一覧
- character impressions一覧

関連:

- API: `GET /api/v1/projects/<project_id>/cinema-novels/bgm`
- API: `POST /api/v1/projects/<project_id>/cinema-novels/bgm`
- API: `GET /api/v1/cinema-novels/<novel_id>/reviews`
- API: `POST /api/v1/cinema-novels/<novel_id>/reviews`
- API: `GET /api/v1/cinema-novels/<novel_id>/lore`
- API: `POST /api/v1/cinema-novels/<novel_id>/lore`
- API: `GET /api/v1/cinema-novels/<novel_id>/character-impressions`

## 関連実装

主なファイル:

- `app/blueprints/cinema_novels/routes.py`
- `app/services/cinema_novel_service.py`
- `app/templates/ui/cinema_novels.html`
- `app/templates/ui/cinema_novel_reader.html`
- `app/static/js/cinema_novels_page.js`
- `app/static/js/cinema_novel_reader.js`
- `app/static/css/screens/cinema_novel.css`

主なモデル:

- `cinema_novel`
- `cinema_novel_chapter`
- `cinema_novel_progress`
- `cinema_novel_review`
- `cinema_novel_lore_entry`
- `cinema_novel_character_impression`

## 今後の整備

正式機能として、以下を優先して整える。

1. UI上で一般ユーザーが制作操作をできないことを確認する。
2. API側でも制作操作がプロジェクト管理権限に限定されていることを確認する。
3. 一覧画面で、制作導線と閲覧導線をロールごとに整理する。
4. READMEにシネマノベルの概要を追加する。
5. ショートコミックと通常シネマノベルの違いをUI文言で明確にする。
6. 出力機能の失敗時メッセージと保存先を整理する。

## 決定事項

- シネマノベルは正式機能。
- ショートコミックも正式機能。
- 管理者とプロジェクトユーザーにとっては制作機能かつ閲覧機能。
- 一般ユーザーにとっては閲覧機能のみ。
- 現在実装されているシネマノベル/ショートコミック関連機能はすべてサポート対象。
