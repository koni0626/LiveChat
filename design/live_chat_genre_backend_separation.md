# ライブチャット ジャンル別バックエンド分離設計書

## 1. 目的

ライブチャットに「ジャンル」を導入し、既存の恋愛チャットと新規の学習チャットをバックエンド上で明確に分離する。

学習チャットでは、黒板、板書、教材、確認問題、授業進行など、恋愛チャットとは異なる改造が継続的に入る見込みがある。そのため、既存の恋愛モードに条件分岐を足し続けるのではなく、処理パイプラインを分けて、恋愛モードのデグレードを防ぐ。

## 2. 基本方針

ルームには共通項目として `genre` を持たせる。

- `romance`: 既存のライブチャット。恋愛、ラブコメ、施設利用、キャラクター関係性、シャッターチャンスを重視する。
- `learning`: 学習チャット。授業、板書、教材、図解、確認問題、理解確認を重視する。

ルーム、セッション、メッセージ保存、画像保存、APIレスポンス形式は共通化する。

一方で、以下はジャンル別に分離する。

- コンテキスト収集
- 会話生成プロンプト
- DirectorAI
- 画像生成プロンプト
- シャッターチャンス
- 記憶更新
- 会話評価
- 施設情報の投入有無
- キャラクター関係性の扱い

## 3. 現状の問題

現在のライブチャットは、恋愛・日常イベントCG向けの情報が同じパイプラインに集約されている。

主な混入要素は以下。

- 施設情報
- ワールド活動情報
- キャラクター同士の関係性
- プレイヤーとの親密度
- ラブコメ寄りの会話評価
- シャッターチャンス
- 写真映えするイベントCG向け画像プロンプト

そのため、ユーザーが「黒板で説明して」「板書を見ながら確認したい」と入力しても、画像生成側では「キャラクターの魅力的な会話シーン」として扱われやすい。

学習モードでは、黒板や教材を主役にしたい。恋愛モードと同じ材料を渡し続けると、施設、関係性、ラブコメ演出がノイズになる。

## 4. 推奨アーキテクチャ

`LiveChatService` の下にジャンルルーターを置き、実処理をジャンル別サービスへ委譲する。

```text
LiveChatService
  └─ LiveChatGenreRouter
       ├─ RomanceLiveChatBackend
       │    ├─ RomanceContextBuilder
       │    ├─ RomanceConversationEngine
       │    ├─ RomanceDirector
       │    ├─ RomanceVisualPromptBuilder
       │    ├─ RomanceSceneChoiceService
       │    └─ RomanceMemoryUpdater
       │
       └─ LearningLiveChatBackend
            ├─ LearningContextBuilder
            ├─ LearningConversationEngine
            ├─ LearningDirector
            ├─ LearningVisualPromptBuilder
            ├─ LearningSceneChoiceService
            └─ LearningMemoryUpdater
```

既存の `LiveChatConversationService`、`LiveChatContextService`、`live_chat_prompt_*` は、まず恋愛モード側として扱う。

学習モードは新規サービスを追加する。既存サービスを直接改造して共用しない。

## 5. 共通にするもの

以下はジャンルで分けずに共通利用する。

| 項目 | 方針 |
|---|---|
| `LiveChatRoom` | `genre` を追加する。 |
| `ChatSession` | 既存のセッションモデルを使う。 |
| `ChatMessage` | 既存のメッセージ保存を使う。 |
| `SessionImage` | 既存の画像保存を使う。 |
| ルーム作成・更新API | `genre` を受け取る。 |
| セッション作成API | ルームの `genre` をスナップショットへ保存する。 |
| UIの基本画面 | 同じチャット画面を使い、表示内容だけジャンルで変える。 |
| 課金・ポイント処理 | 原則共通。必要なら学習モードの単価を後で分ける。 |

## 6. 分離するもの

### 6.1 コンテキスト

恋愛モードでは既存通り、以下を重視する。

- 施設情報
- ワールド活動
- キャラクター関係性
- プレイヤーとの記憶
- 親密度
- 衣装
- 現在の場面

学習モードでは、以下を基本コンテキストとする。

- ルームの学習テーマ
- 参加キャラクター
- プレイヤーの直近発言
- 直近の会話履歴
- 授業の進行状態
- 黒板に書くべき要点
- 確認問題
- プレイヤーが理解できていない点

学習モードでは原則として以下を渡さない。

- 施設情報
- 詳細なワールドマップ
- キャラクター同士の恋愛関係性
- 親密度評価
- ラブコメ向けのシャッターチャンス
- ワールドニュースやFeed由来の話題

### 6.2 会話生成

恋愛モードでは、現在のラブコメ会話、親密度、場面進行を維持する。

学習モードでは、会話生成の目的を以下に変える。

- プレイヤーの質問を授業テーマとして受け取る
- キャラクターが先生役として説明する
- 黒板に書く要点を会話内で明示する
- 難しい内容は例え話、段階説明、確認問題に分解する
- キャラクター同士の掛け合いは補助に留める
- 恋愛的な照れ、身体的ハプニング、施設話題を主軸にしない

### 6.3 DirectorAI

恋愛モードのDirectorAIは、関係性、感情トーン、ラブコメ展開、シャッターチャンスを管理する。

学習モードのDirectorAIは、授業設計を管理する。

学習モードのDirectorAIが持つべき状態:

```json
{
  "lesson_topic": "量子力学の二重スリット実験",
  "lesson_stage": "導入 / 説明 / 例示 / 確認 / まとめ",
  "board_plan": ["二重スリット", "波と粒子", "観測の影響"],
  "learner_confusion": ["観測すると結果が変わる理由"],
  "next_teaching_action": "図で説明する",
  "check_question": "観測前と観測後で何が変わる？"
}
```

恋愛モードのDirectorAIと同じJSON構造を無理に使わない。

### 6.4 画像生成

恋愛モードでは、キャラクターの魅力、場面のインパクト、ラブコメ的な絵作りを優先する。

学習モードでは、以下を優先する。

- 黒板が画面内にはっきり見える
- 板書が主役になる
- キャラクターは先生役として黒板の横に立つ
- 吹き出しは禁止
- 字幕、UI、ロゴ、透かしは禁止
- 黒板、ノート、教材、図解にある自然な文字は許可する

画像プロンプトには、自由文だけでなく `board_items` を構造化して渡すことを推奨する。

```json
{
  "scene": "ラプラスが黒板の前で量子力学を説明している",
  "characters": ["ラプラス"],
  "board_items": [
    "二重スリット実験",
    "電子は波のように広がる",
    "観測すると結果が変わる"
  ],
  "visual_goal": "黒板の要点を見ながら一緒に確認できる授業シーン"
}
```

### 6.5 シャッターチャンス

恋愛モードでは、現在のシャッターチャンスを維持する。

学習モードでは、名称と意味を変える。

候補:

- 板書更新
- 図解生成
- 例題シーン
- まとめ画像
- 確認問題カード

学習モードでは「写真映えする瞬間」を探すのではなく、「理解を助ける画像化ポイント」を探す。

### 6.6 記憶更新

恋愛モードでは、現在のキャラクター記憶、親密度、関係性の記録を維持する。

学習モードでは、恋愛的な思い出ではなく、学習履歴を記録する。

学習モードで記録したい情報:

- プレイヤーが質問したテーマ
- 理解済みの内容
- つまずいた内容
- 次回復習すべき内容
- 好みの説明方法
- よく使う教材形式

例:

```json
{
  "topic": "量子力学",
  "understood": ["二重スリット実験の概要"],
  "needs_review": ["観測問題"],
  "preferred_style": "図解と例え話があると理解しやすい"
}
```

## 7. DB設計

`live_chat_room` に `genre` を追加する。

```text
genre: string, not null, default "romance"
```

既存ルームはすべて `romance` として扱う。

ルームスナップショットにも `genre` を保存する。

```json
{
  "id": 1,
  "title": "旧メンバー",
  "genre": "romance",
  "selected_character_ids": [1, 2, 3]
}
```

既存セッションは、スナップショットに `genre` がない場合 `romance` とみなす。

## 8. API設計

ルーム作成・更新APIに `genre` を追加する。

```json
{
  "title": "量子力学教室",
  "genre": "learning",
  "selected_character_ids": [2],
  "conversation_objective": "量子力学を黒板でわかりやすく説明する"
}
```

レスポンスにも `genre` を含める。

```json
{
  "id": 10,
  "title": "量子力学教室",
  "genre": "learning",
  "status": "published"
}
```

## 9. UI設計

ルーム作成・編集画面にジャンル選択を追加する。

- 恋愛
- 学習

初期値は `恋愛`。

学習を選んだ場合、ルーム説明や目的欄のプレースホルダーを学習向けに変える。

例:

- 学習テーマ
- 先生役キャラクター
- 授業の目的
- 板書してほしい内容

チャット画面の基本UIは共通でよい。ただし、学習モードでは以下を変える。

- シャッターチャンス表示を学習用表示にする
- 画像生成ボタンの文言を「板書画像」「図解」寄りにする
- 施設移動やラブコメ向け候補は出さない

## 10. 実装ステップ

### Phase 1: ジャンル導入

- `LiveChatRoom` に `genre` を追加
- ルーム作成・更新・シリアライズに `genre` を追加
- セッション作成時に `room_snapshot_json` へ `genre` を保存
- 既存ルーム・既存セッションは `romance` として扱う
- UIにジャンル選択を追加

### Phase 2: ルーター導入

- `LiveChatGenreRouter` を追加
- `romance` は既存サービスへ委譲
- `learning` は新規サービスへ委譲
- APIのレスポンス形式は既存と互換にする

### Phase 3: 学習コンテキスト分離

- `LearningContextBuilder` を追加
- 施設情報を渡さない
- キャラクター関係性を渡さない
- 学習テーマ、会話履歴、授業状態を中心にする

### Phase 4: 学習会話・Director分離

- `LearningConversationEngine` を追加
- `LearningDirector` を追加
- 授業進行、板書項目、確認問題を管理する

### Phase 5: 学習画像生成分離

- `LearningVisualPromptBuilder` を追加
- 黒板、板書、図解、教材を主役にする
- `board_items` を構造化して渡す
- 吹き出しは禁止、黒板文字は許可する

### Phase 6: 学習記憶分離

- 学習履歴メモリを追加
- 恋愛モードの親密度・関係性記憶とは別管理にする

## 11. デグレード防止策

恋愛モードのデグレードを防ぐため、以下を守る。

- 既存サービスを直接学習向けに書き換えない
- 既存プロンプトへ学習用条件を大量追加しない
- `genre` がない場合は必ず `romance` 扱いにする
- 既存APIレスポンス形式を維持する
- 学習サービスは新規ファイル中心で追加する
- 共通化は保存処理、シリアライズ、リポジトリなど副作用の少ない部分に限定する

## 12. 実装対象候補ファイル

### 共通・ルーム

- `app/models/live_chat_room.py`
- `app/repositories/live_chat_room_repository.py`
- `app/services/live_chat_room_service.py`
- `app/services/live_chat_session_workflow_service.py`
- `app/templates/ui/live_chat_room_edit.html`
- `app/static/js/live_chat_room_edit_page.js`

### 既存恋愛モードとして温存する候補

- `app/services/live_chat_conversation_service.py`
- `app/services/live_chat_context_service.py`
- `app/services/live_chat_prompt_text_support.py`
- `app/services/live_chat_prompt_visual_support.py`
- `app/services/live_chat_text_support.py`

### 学習モードで新規追加する候補

- `app/services/live_chat_genre_router.py`
- `app/services/learning_live_chat_context_service.py`
- `app/services/learning_live_chat_conversation_service.py`
- `app/services/learning_live_chat_director_service.py`
- `app/services/learning_live_chat_prompt_text_support.py`
- `app/services/learning_live_chat_prompt_visual_support.py`
- `app/services/learning_live_chat_memory_service.py`

## 13. 判断

バックエンド完全分離は可能。

最も安全な形は、既存のライブチャット処理を恋愛モードとして温存し、学習モードはジャンルルーターから新規サービスへ委譲する構成である。

この構成なら、学習モード側で黒板、板書、教材、授業進行、確認問題、学習記憶を大きく改造しても、恋愛モードへの影響を最小化できる。
