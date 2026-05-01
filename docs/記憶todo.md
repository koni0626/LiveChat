# 記憶機能 TODO

## 進捗（2026-05-01）

- [x] `user.player_name` カラム追加（モデル）
- [x] `character_user_memory` テーブル追加（モデル）
- [x] マイグレーション追加（`a13f9b7c2d10_add_player_name_and_character_user_memory.py`）
- [x] `GET /api/v1/auth/me` に `player_name` を含める
- [x] `PATCH /api/v1/auth/me/player-name` 追加
- [x] PC/スマホのログアウト導線付近に「名前変更」導線追加
- [x] チャットルーム開始時のプレイヤー名入力を廃止（ユーザー設定名を使用）
- [x] ストーリー開始時のプレイヤー名入力を廃止（ユーザー設定名を使用）
- [x] `CharacterUserMemoryService` 実装
- [x] ライブチャット context にキャラクター別ユーザー記憶を注入
- [x] ライブチャット prompt にキャラクター別ユーザー記憶を反映
- [x] ライブチャット会話後に記憶更新
- [x] おでかけ完了時に記憶更新
- [x] ストーリー進行時に記憶更新

## 未完了（次フェーズ）

- [ ] 記憶更新を AI 構造化出力ベースに強化（`should_remember` / 各フィールド精密更新）
- [ ] ストーリー/おでかけの生成プロンプトへ記憶ブロックを直接注入
- [ ] 記憶 ON/OFF 設定（superuser 管理 + 反映）
- [ ] 記憶の閲覧/編集 UI（管理者向け）
- [ ] テスト整備（サービス単体 + 主要 API + 回帰）
