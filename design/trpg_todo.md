# TRPG化 TODO

## 0. 前提

- [x] 既存のルーム / ライブチャット系コードは削除しない
- [x] 新しく `story` / `story_session` 系を並行実装する
- [x] 新UIが動くまでは旧UIを残す
- [x] 画像生成はMVPでは後回しにする
- [x] ただし画像生成を後で入れられるよう、状態とテーブルには余地を残す

## 1. モデル / DB

- [x] `Story` モデルを作成する
- [x] `StorySession` モデルを作成する
- [x] `StorySessionState` モデルを作成する
- [x] `StoryMessage` モデルを作成する
- [x] `StoryRollLog` モデルを作成する
- [x] `StoryImage` モデルを作成する
- [x] `app/models/__init__.py` に新モデルを追加する
- [x] マイグレーションまたはDB初期化手順を追加する
- [x] 既存テーブルに影響しないことを確認する

## 2. Repository / Service

- [x] `StoryRepository` を作成する
- [x] `StorySessionRepository` を作成する
- [x] `StorySessionStateRepository` を作成する
- [x] `StoryMessageRepository` を作成する
- [x] `StoryRollLogRepository` を作成する
- [x] `StoryImageRepository` を作成する
- [x] `StoryService` を作成する
- [x] `StorySessionService` を作成する
- [x] `StoryStateService` を作成する
- [x] 既存 `LiveChatRoomService` / `ChatSessionService` から移植できる処理を整理する

## 3. URL / API

- [x] `/projects/<project_id>/stories` のAPIを作成する
- [x] `/projects/<project_id>/stories/<story_id>` のAPIを作成する
- [x] `/projects/<project_id>/story-sessions` のAPIを作成する
- [x] `/projects/<project_id>/story-sessions/<session_id>` のAPIを作成する
- [x] セッション開始APIを作成する
- [x] メッセージ送信APIを作成する
- [x] 選択肢実行APIを作成する
- [x] Markdown解析APIを作成する

## 4. UIルート / メニュー

- [x] ストーリー一覧ページのUIルートを追加する
- [x] ストーリー新規作成ページのUIルートを追加する
- [x] ストーリー編集ページのUIルートを追加する
- [x] セッション一覧ページのUIルートを追加する
- [x] セッション画面のUIルートを追加する
- [x] 左メニューに「ストーリー」を追加する
- [x] 左メニューに「セッション」を追加する
- [x] 新UIが動いた後、旧「ルーム」「ライブチャット」をメニューから隠す

## 5. ストーリー管理UI

- [x] ストーリー一覧テンプレートを作成する
- [x] ストーリー編集テンプレートを作成する
- [x] 基本情報フォームを作成する
- [x] Markdown設定エディタを作成する
- [x] Markdown解析ボタンを作成する
- [x] 解析結果プレビューを作成する
- [x] `config_markdown` を保存できるようにする
- [x] `config_json` を保存できるようにする
- [x] 公開状態を変更できるようにする

## 6. Markdown設定AI解析

- [x] Markdownを構造化JSONに変換するプロンプトを作成する
- [x] 返却JSONスキーマを定義する
- [x] `story_mode` を抽出する
- [x] `premise` を抽出する
- [x] `tone` を抽出する
- [x] `choice_policy` を抽出する
- [x] `relationship_policy` を抽出する
- [x] `event_deck` を抽出する
- [x] `dice_policy` を抽出する
- [x] `visual_policy` を抽出する
- [x] AI出力を検証・正規化する
- [x] 解析失敗時のフォールバックを作る

## 7. セッション開始

- [x] ストーリーからセッションを開始できるようにする
- [x] プレイヤー名を入力できるようにする
- [x] ストーリー設定を `story_snapshot_json` に保存する
- [x] `initial_state_json` から `story_session_state` を初期化する
- [x] 初期メッセージを生成または保存する
- [x] セッション一覧に表示する

## 8. セッション画面

- [x] セッション画面テンプレートを作成する
- [x] 会話ログを表示する
- [x] ユーザー入力欄を作成する
- [x] 3択を表示する
- [x] 現在地を表示する
- [x] 危険度を表示する
- [x] 親密度 / 信頼度 / 緊張度を表示する
- [x] 所持品 / フラグを表示する
- [x] サイコロ結果を表示できる枠を用意する
- [x] 画像表示枠は用意するが、MVPでは生成を後回しにする

## 9. directionAI / GM

- [x] directionAI用のプロンプトを作成する
- [x] ユーザー入力を行動として解釈する
- [x] 現在のセッション状態を参照する
- [x] イベント発火の判断を行う
- [x] キャラクターの気まぐれ行動を発生させる
- [x] 失敗してもおいしい展開を生成する
- [x] 未解決スレッドを参照する
- [x] 関係性に応じた展開を生成する
- [x] `gm_result` を返す
- [x] `state_patch` を返す
- [x] `next_choices` を返す

## 10. state_patch

- [x] state_patchのスキーマを定義する
- [x] state_patchを検証する
- [x] 数値変化の上限を設定する
- [x] 存在しないキャラクターや場所への参照を防ぐ
- [x] アイテムID重複を防ぐ
- [x] 所持品追加を適用する
- [x] 装備変更を適用する
- [x] 親密度 / 信頼度 / 緊張度の変化を適用する
- [x] 危険度 / 進行度の変化を適用する
- [x] フラグ追加を適用する
- [x] 未解決スレッド更新を適用する
- [x] 適用後の状態を保存する

## 11. セリフ自動生成

- [x] characterAI用のプロンプトを作成する
- [x] `gm_result` を事実として扱わせる
- [x] キャラクターがGM裁定を上書きしないようにする
- [x] キャラクター設定と口調を反映する
- [x] 関係性の状態をセリフに反映する
- [x] キャラクターの気まぐれ行動後の反応を生成する
- [x] 生成したセリフを `story_message` に保存する

## 12. 選択肢

- [x] 3択を基本にする
- [x] 探索 / 親密 / 危険の役割を持たせる
- [x] 関係性によって選択肢を変化させる
- [x] 危険度によって選択肢を変化させる
- [x] 未解決スレッドを選択肢に反映する
- [x] 選択肢を `state_json` または `story_message.metadata_json` に保存する
- [x] 選択肢実行時にdirectionAIへ渡す

## 13. サイコロ

- [x] ダイス式パーサーを作成する
- [x] `1d6` を振れるようにする
- [x] `2d6` を振れるようにする
- [x] `1d20` を振れるようにする
- [x] `1d100` を振れるようにする
- [x] 修正値を扱えるようにする
- [x] 目標値判定を行う
- [x] 結果を `story_roll_log` に保存する
- [x] 結果をメッセージまたはUIに表示する
- [x] 失敗してもおいしい展開へつなげる

## 14. アイテム / 装備

- [x] アイテム表現のスキーマを決める
- [x] `owner` を管理する
- [x] `equipped` を管理する
- [x] `visible` を管理する
- [x] `visual_description` を管理する
- [x] `visibility_priority` を管理する
- [x] アイテムを拾う処理を作る
- [x] アイテムを渡す処理を作る
- [x] アイテムを装備する処理を作る
- [x] 次回の画像生成に使えるよう `visual_state` に反映する

## 15. メール連動

- [ ] セッション中の重要イベントをメール候補として記録する
- [ ] 手を取った、かばった、剣を渡した等を拾う
- [ ] メール生成時に `story_session_state` を参照する
- [ ] メール本文にセッションの余韻を反映する
- [ ] 既存メール機能との接続方針を決める

## 16. 後回し機能

- [x] シーン画像生成
- [x] 画風基準画像のUI
- [x] 画像内伏線
- [x] セッション画像生成の品質・サイズをユーザー設定の `default_quality` / `default_size` に合わせる
- [ ] `story_event_definition` の個別テーブル化
- [ ] `story_item_definition` の個別テーブル化
- [ ] `story_choice_log` の個別テーブル化
- [ ] `story_state_history` の個別テーブル化
