# キャラクター自律行動ログ

更新日: 2026-05-09

## 位置づけ

キャラクター自律行動ログは正式採用機能とする。

まずはスケジューラではなく、Flask CLIコマンドで実行する。ユーザー操作なしにキャラクターが少し動いた痕跡を作り、FeedやWorld Newsへ流す。

## 目的

- 世界がユーザー操作なしでも少し動いている感覚を作る
- キャラクターの生活、仕事、失敗、観測、噂をFeed/World Newsに残す
- 次のライブチャットやおでかけの話題になる素材を作る

## コマンド

```powershell
python -m flask --app app:create_app generate-character-actions --project-id 1 --count 3
```

出力先を選ぶ:

```powershell
python -m flask --app app:create_app generate-character-actions --project-id 1 --count 3 --target feed
python -m flask --app app:create_app generate-character-actions --project-id 1 --count 3 --target news
python -m flask --app app:create_app generate-character-actions --project-id 1 --count 3 --target both
```

保存せずに確認する:

```powershell
python -m flask --app app:create_app generate-character-actions --project-id 1 --count 3 --dry-run
```

AIを使わずフォールバック文で生成する:

```powershell
python -m flask --app app:create_app generate-character-actions --project-id 1 --count 3 --no-ai
```

Feed投稿にラブコメ目撃写真風の画像を付ける:

```powershell
python -m flask --app app:create_app generate-character-actions --project-id 1 --count 3 --target feed --with-images
```

FeedとWorld Newsを作り、Feed側に画像を付ける:

```powershell
python -m flask --app app:create_app generate-character-actions --project-id 1 --count 3 --target both --with-images
```

## オプション

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--project-id` | 必須 | 対象プロジェクトID。 |
| `--count` | `3` | 生成する行動ログ数。最大10件。 |
| `--target` | `feed` | `feed`、`news`、`both` から選ぶ。 |
| `--status` | `published` | Feed投稿の状態。`published` または `draft`。 |
| `--user-id` | project owner | 作成者ユーザーID。省略時はプロジェクト所有者。 |
| `--dry-run` | false | 保存せずプレビューする。 |
| `--no-ai` | false | AIを呼ばず、決定的なフォールバック文で生成する。 |
| `--with-images` | false | Feed投稿に画像を生成する。 |
| `--image-size` | `1536x1024` | 生成画像サイズ。 |
| `--image-quality` | app setting | 生成画像品質。省略時はアプリ設定を使う。 |

## 現在の保存先

### Feed

`target=feed` または `target=both` の場合、`feed_post` に投稿を作る。

`generation_state_json` には以下を入れる。

- `source: autonomous_character_action`
- `action_type`
- `generated_at`
- `raw_item`

`--with-images` を指定した場合、Feed投稿に `feed_image` asset を紐づける。

画像は「ラブコメ目撃写真」風を目指す。

- インパクトのあるSNS目撃写真/イベントCG
- キャラクターの感情が読み取れる
- 照れ、驚き、嫉妬、嬉しさ、平静を装う感じ
- 偶然の距離感、目線、手が触れそうな瞬間、誤解されそうな状況
- 上品で非露骨なロマンティックコメディ表現
- キャラクター基準画像がある場合は、同一性参照として使う

### World News

`target=news` または `target=both` の場合、`world_news_item` にニュースを作る。

`source_type` は `autonomous_character_action`。

`target=both` の場合、World News から Feed投稿IDを参照する。

現在、`--with-images` の画像生成対象はFeed投稿。`target=news` のみの場合は画像生成しない。

## 現在の生成内容

AI使用時は、以下のような行動ログ候補をJSONで作る。

- 施設で小さなトラブルを起こす
- 誰かに目撃される
- 店や仕事で新しい試みをする
- 深夜に意味深な行動をする
- 別キャラと小さなやり取りをする
- 都市の噂になる
- うっかり本音が漏れる
- 何かを観測、調査、記録する

AIが使えない場合や `--no-ai` の場合は、キャラクターと場所を使ったフォールバック文を作る。

## 関連実装

- CLI: `app/__init__.py`
- Service: `app/services/autonomous_character_action_service.py`
- Tests: `tests/test_autonomous_character_action_service.py`

## 今後の拡張

- キャラごとの自律行動頻度
- 一度出たログと似た内容の抑制
- Feed/World News以外に、ライブチャットの話題メモへ注入
- おでかけ、メール、記憶への反映
- スケジューラ化
- キャラ同士の関係性変化
- 画像生成付きログ
