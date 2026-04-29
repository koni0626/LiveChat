# TRPG化 設計書

## 1. 目的

既存のライブチャットを、キャラクターと会話するだけの体験から、ユーザーがキャラクターと一緒に物語を攻略する体験へ拡張する。

目指す体験は以下。

- ユーザーの入力や選択が、現在地、危険度、親密度、所持品、フラグに反映される
- 物語が淡々と進まず、謎、事件、戦闘、宝箱、罠、秘密、恋愛イベントが起きる
- キャラクターとの会話やセリフ自動生成は残す
- directionAIをゲームマスターとして扱い、状況裁定と展開制御を行う
- ストーリー設定をMarkdownで自由に書き、AIが構造化してJSON保存する
- 画像はキャラクター固定ではなく、現在の場面を表す画像として扱う
- 画風は基準画像をもとに統一する

## 2. 基本方針

既存のルーム / チャットルーム系コードはすぐに壊さない。

新しく以下の概念を作る。

| 旧概念 | 新概念 | 役割 |
| --- | --- | --- |
| ルーム | ストーリー | 物語、シナリオ、ルール、設定テンプレート |
| チャットルーム / ライブチャット | セッション | ユーザーごとに進行する実プレイ |
| 会話ディレクター | directionAI / GM | 状況裁定、イベント発火、選択肢設計、状態更新 |
| AIキャラクター | characterAI | キャラクター本人としてセリフを話す |

UI上からは「ルーム」「チャットルーム」「ライブチャット」という表示を消し、「ストーリー」「セッション」を表示する。

ただし、既存の以下は参考・移植元として使う。

- `live_chat_room`
- `chat_session`
- ライブチャット画面
- ルーム編集画面
- 会話生成処理
- 画像生成処理
- メール生成処理
- セッション状態管理

## 3. ストーリー

ストーリーは、セッション開始前のシナリオテンプレート。

持つべき情報:

- タイトル
- 説明
- メインキャラクター
- プレイヤーの役割
- 舞台
- ジャンル
- 目的
- Markdown設定本文
- AI構造化済みJSON
- 初期セッション状態
- イベントデッキ
- 選択肢方針
- 恋愛 / 親密方針
- 危険度方針
- サイコロ方針
- 画像方針
- 公開状態
- 並び順

DBイメージ:

```text
story
- id
- project_id
- character_id
- created_by_user_id
- title
- description
- status
- story_mode
- config_markdown
- config_json
- initial_state_json
- style_reference_asset_id
- main_character_reference_asset_id
- sort_order
- created_at
- updated_at
- deleted_at
```

## 4. セッション

セッションは、ストーリーから開始されたユーザーごとの実プレイ。

持つべき情報:

- 紐づくストーリー
- 所有ユーザー
- セッションタイトル
- プレイヤー名
- ステータス
- ストーリー設定スナップショット
- 現在のセッション状態
- 現在表示する画像
- 会話ログ
- 選択肢
- サイコロ履歴
- 画像生成履歴
- メール生成との関連

DBイメージ:

```text
story_session
- id
- project_id
- story_id
- owner_user_id
- title
- status
- privacy_status
- player_name
- active_image_id
- story_snapshot_json
- settings_json
- created_at
- updated_at
- deleted_at
```

## 5. セッション状態

セッション状態は、攻略中の盤面として扱う。

例:

```json
{
  "game_state": {
    "mode": "dungeon_trpg",
    "location": "忘却回廊・入口",
    "progress": 0,
    "danger": 20,
    "inventory": [],
    "flags": [],
    "open_threads": []
  },
  "relationship_state": {
    "affection": 10,
    "trust": 10,
    "tension": 0,
    "romance_stage": 0
  },
  "event_state": {
    "turn_count": 0,
    "last_event_turn": 0,
    "used_events": [],
    "pending_event": null
  },
  "choice_state": {
    "last_choices": [],
    "policy": "explore_romance_risk"
  },
  "visual_state": {
    "active_visual_type": "location",
    "active_subject": "忘却回廊・入口"
  }
}
```

アイテムや装備は、単に所持品リストに入れるだけではなく、誰が持っているか、装備中か、画像に出すべきかを管理する。

例:

```json
{
  "id": "silver_sword",
  "name": "銀の剣",
  "type": "weapon",
  "owner": "noa",
  "equipped": true,
  "visible": true,
  "visual_description": "淡く青白く光る細身の銀の剣",
  "visibility_priority": 80
}
```

画像生成時は、現在地、登場キャラ、服装、装備中アイテム、見える所持品、直近の行動、画風基準画像を参照する。

例えばノアが剣を持っている状態なら、次回以降の画像生成プロンプトに「ノアは淡く青白く光る細身の銀の剣を手に持っている」を含める。

## 6. Markdown設定とAI構造化

固定フォームだけでTRPG設定を作るのは厳しいため、ストーリー設定はMarkdown自由記述を主にする。

基本フロー:

1. ユーザーがMarkdownで自由に設定を書く
2. 「設定を解析」する
3. AIがMarkdownを分類してJSON化する
4. 解析結果の要約を画面に表示する
5. ユーザーが確認して保存する
6. セッション開始時にJSONをスナップショットする

Markdown例:

```md
# 忘却回廊

## 概要
ノアと一緒に、記憶を食べる地下迷宮を探索する。

## 雰囲気
少し怖い。けれどノアとの距離が少しずつ近づく。
恋愛要素は中程度。

## 主なイベント
- 宝箱を見つける
- 影のモンスターが現れる
- ノアが過去を隠している
- 休憩部屋で手当てをする
- 魔法の霧で本音が漏れる

## 選択肢方針
3択。探索 / 親密 / 危険。
```

構造化JSON例:

```json
{
  "story_mode": "dungeon_trpg",
  "premise": "ノアと地下迷宮を探索する",
  "tone": ["mystery", "romance", "slightly_spicy"],
  "choice_policy": {
    "count": 3,
    "roles": ["explore", "romance", "risk"]
  },
  "relationship_policy": {
    "romance_intensity": 2,
    "allowed": ["hand_holding", "close_distance", "teasing", "care_scene"]
  },
  "event_deck": [],
  "visual_policy": {},
  "dice_policy": {}
}
```

固定フォームは補助にする。

固定で持つ項目:

- タイトル
- メインキャラクター
- 公開状態
- ストーリーモード
- 恋愛強度
- 危険度
- 選択肢数
- 基準画像

## 7. directionAI / GM

directionAIはゲームマスターとして扱う。

役割:

- 現在地を管理する
- ユーザー入力を行動として解釈する
- イベントを発火する
- 宝箱、アイテム、罠、モンスター、謎を出す
- 選択肢を設計する
- サイコロ判定の要否を決める
- 成功 / 失敗を裁定する
- セッション状態を更新する
- 場面画像の内容を決める
- 恋愛イベントの濃さを制御する
- 同じ展開が続かないようにする

重要な分離:

```text
directionAI = 状況、裁定、イベント、ルール
characterAI = キャラクター本人のセリフ
```

characterAIはGMの裁定を上書きしない。

## 8. 状態更新JSON

状態更新は、AIがDBを直接書き換えるのではなく、directionAIが状態更新案JSONを返し、アプリ側が検証してセッション状態に反映する。

基本フロー:

```text
ユーザー入力 / 選択肢 / 直近セリフ
→ directionAIが状況を裁定する
→ state_patchを含むJSONを返す
→ アプリ側が検証・正規化する
→ session_state_jsonへ反映する
→ 次回のセリフ、選択肢、画像生成に使う
```

例:

```json
{
  "narration": "あなたは床に落ちていた淡く光る銀の剣を拾い、ノアに手渡した。",
  "state_patch": {
    "inventory": {
      "add": [
        {
          "id": "silver_sword",
          "name": "銀の剣",
          "type": "weapon",
          "owner": "noa",
          "equipped": true,
          "visible": true,
          "visual_description": "淡く青白く光る細身の銀の剣",
          "visibility_priority": 80
        }
      ]
    },
    "visual_state": {
      "character_visible_items": {
        "noa": ["silver_sword"]
      }
    },
    "relationship_state": {
      "trust_delta": 2
    }
  },
  "next_choices": [
    {
      "label": "剣の反応を見る",
      "role": "explore"
    },
    {
      "label": "ノアに似合うと伝える",
      "role": "romance"
    },
    {
      "label": "奥へ進む",
      "role": "risk"
    }
  ]
}
```

アプリ側で検証すること:

- JSON形式が正しいか
- `owner` が存在するキャラクターまたはプレイヤーか
- `type` が許可されたアイテム種別か
- 同じ `id` のアイテムが重複していないか
- 数値変化が許容範囲内か
- 存在しない場所やフラグを参照していないか
- キャラクター設定やストーリー設定に反していないか
- 画像に出すアイテムが多すぎないか

AIは状態更新の提案者、アプリは審判・保存係とする。

セリフ内容から状態更新を推測する場合も、基本的にはdirectionAIの裁定結果を正とする。

## 9. セリフ自動生成

セリフ自動生成は残す。

TRPG化後の流れ:

```text
ユーザー入力
→ directionAIが状況を裁定する
→ セッション状態を更新する
→ characterAIがキャラクター本人としてセリフを生成する
→ 必要に応じて選択肢、画像、メールへつなげる
```

characterAIへの入力例:

```json
{
  "character": "ノア",
  "session_state": {
    "location": "忘却回廊・第二層",
    "danger": 45,
    "affection": 32,
    "tension": 18
  },
  "gm_result": {
    "event": "罠を避けるため、二人は狭い壁際に身を寄せた",
    "state_changes": ["danger_down", "tension_up", "affection_up"],
    "next_mood": "照れと緊張、しかし探索は続く"
  }
}
```

## 10. 選択肢

選択肢は3択を基本にする。

標準役割:

1. 探索
2. 親密
3. 危険 / 謎 / 対決

ダンジョン例:

```text
古い宝箱がある

1. 罠を調べる
2. ノアに任せる
3. すぐに開ける
```

モンスター例:

```text
影のモンスターが現れた

1. 戦う
2. 逃げる
3. ノアをかばって様子を見る
```

選択肢の結果はセッション状態に反映する。

- 探索: `progress`、`inventory`、`open_threads`
- 親密: `affection`、`trust`、`tension`
- 危険: `danger`、`flags`、`pending_event`

## 11. 行動入力

以下は単なる会話ではなく、行動として扱う。

- 触れる
- 撫でる
- 近づく
- 手を取る
- 手を握る
- 見つめる
- 外へ出る
- 調べる
- 開ける
- 拾う
- 戦う
- 逃げる
- 隠れる
- 追う
- 戻る

行動入力は、場面更新、状態更新、選択肢生成、画像生成に使う。

## 12. サイコロ

サイコロは実装する。

ただし、単に乱数を振るのではなく、結果をセッションログと状態に残す。

対応例:

- `1d6`
- `2d6`
- `1d20`
- `1d100`
- 固定修正値
- 能力値修正

判定例:

```text
罠を調べる
1d20 + 観察力 >= 12 なら成功
```

保存例:

```json
{
  "formula": "1d20+3",
  "dice": [
    { "sides": 20, "result": 14 }
  ],
  "modifier": 3,
  "total": 17,
  "target": 12,
  "outcome": "success",
  "reason": "罠を調べる"
}
```

表示方針はストーリー設定で切り替える。

```json
{
  "dice_policy": {
    "enabled": true,
    "visibility": "visible"
  }
}
```

## 13. イベントデッキ

驚きを作るため、ストーリーにイベントデッキを持たせる。

ダンジョン例:

- 宝箱
- アイテム
- 罠
- モンスター
- 隠し部屋
- ボス
- 休憩地点
- 魔法の霧

他ジャンル例:

- 学園ミステリー
- 都市伝奇
- 館もの
- 冒険ファンタジー
- 宇宙船サバイバル
- 吸血鬼ゴシック恋愛
- スパイ潜入
- 無人島サバイバル
- 怪盗 / 宝探し
- 温泉旅館ミステリー

共通エンジンは同じにして、ジャンルごとにイベントデッキと語彙を変える。

## 14. 恋愛・艶っぽさ

恋愛要素は入れる。

ただし、単に甘い返答を増やすのではなく、探索、危険、信頼の報酬として扱う。

段階例:

- Stage 0: 軽い好意、照れ、距離感
- Stage 1: 手をつなぐ、近づく、見つめる
- Stage 2: 密着、弱音、本音、からかい
- Stage 3: 休憩地点での親密な会話、艶っぽい緊張

使いやすい場面:

- 暗い通路で手をつなぐ
- 罠を避けるために密着する
- 魔法の霧で本音が漏れる
- 服や髪が濡れる
- 休憩部屋で弱音を見せる
- 扉の条件が信頼や心拍に関係する

注意:

- キャラクターの人格を壊さない
- 同意や自然な流れを重視する
- 露骨な描写だけに寄せない
- 事件、謎、攻略へ戻す導線を残す

## 15. 画像方針

新しいセッションでは、画像を「常にAIキャラクターの画像」として扱わない。

画像は現在の場面を表すものにする。

表示対象例:

- キャラクター
- 場所
- 宝箱
- アイテム
- モンスター
- 罠
- 地図
- 扉
- 事件現場
- 親密イベント
- 戦闘中の構図

画像生成時に参照する状態:

- 現在地
- 場所の雰囲気
- 登場キャラクター
- キャラクターの服装
- キャラクターの装備中アイテム
- 見える所持品
- モンスターや宝箱などの場面要素
- 直近の行動
- 直近のGM裁定
- 画風基準画像

`active_image_id` 相当の意味:

```text
旧: 現在表示するキャラクター画像
新: 現在表示するシーン画像
```

## 16. 画風基準画像

画風統一のため、ストーリーに基準画像を持たせる。

シンプルな初期案:

```text
style_reference_asset_id
main_character_reference_asset_id
```

画像生成時は、基準画像の媒体、写実度、ライティング、色調、質感を維持する。

方針例:

```json
{
  "visual_policy": {
    "style_reference_asset_id": null,
    "main_character_reference_asset_id": null,
    "use_reference_for_all_scene_images": true,
    "preserve_medium": true,
    "preserve_realism_level": true,
    "allow_style_drift": false
  }
}
```

重要:

- 写真風の基準画像なら写真風を維持する
- 急にイラスト、アニメ、絵画、3D CGへ寄せない
- キャラクター同一性と画風統一は分けて扱う

## 17. スナップショット方針

ストーリー設定はセッション開始時にスナップショットを取る。

理由:

- 進行中セッションの整合性を守る
- ストーリー編集後も既存セッションが急に変化しない
- テスト中に影響範囲を分けられる

必要であれば、管理者操作として「このセッションに最新ストーリー設定を反映」を用意する。

## 18. UI方針

左メニューに以下を表示する。

- ストーリー
- セッション

想定画面:

- ストーリー一覧
- ストーリー新規作成
- ストーリー編集
- Markdown設定解析
- セッション一覧
- セッション開始
- セッション画面

ストーリー編集画面:

- 基本情報フォーム
- Markdown設定エディタ
- 設定解析ボタン
- 解析結果プレビュー
- 基準画像設定
- 公開状態

セッション画面:

- 現在の場面画像
- 会話ログ
- キャラクター発話
- 3択
- 状態表示
- サイコロ結果表示
- 所持品 / フラグ表示

## 19. テーブル設計

新規テーブルを追加し、旧 `live_chat_room` / `chat_session` 系は残す。

初期実装では以下を基本テーブルとする。

```text
story
story_session
story_session_state
story_message
story_roll_log
story_image
```

### story

ストーリー本体。旧ルーム相当。

```text
id
project_id
character_id
created_by_user_id
title
description
status
story_mode
config_markdown
config_json
initial_state_json
style_reference_asset_id
main_character_reference_asset_id
sort_order
created_at
updated_at
deleted_at
```

役割:

- ストーリー設定の保存
- Markdown原文の保存
- AI構造化済みJSONの保存
- 初期セッション状態の保存
- 基準画像の保存

### story_session

ユーザーごとの実プレイ。旧チャットルーム / セッション相当。

```text
id
project_id
story_id
owner_user_id
title
status
privacy_status
player_name
active_image_id
story_snapshot_json
settings_json
created_at
updated_at
deleted_at
```

役割:

- どのストーリーから始まったかを保持する
- ユーザーごとのセッションを管理する
- セッション開始時のストーリー設定スナップショットを保持する
- 現在表示中のシーン画像を保持する

### story_session_state

セッションの現在状態。

```text
id
session_id
state_json
version
created_at
updated_at
```

役割:

- 現在地
- 進行度
- 危険度
- 親密度
- 所持品
- 装備
- フラグ
- イベント状態
- 選択肢状態
- 画像状態

`story_session` に直接JSONを持たせる案もあるが、状態更新頻度が高いため分ける。

### story_message

会話ログ、地の文、GMメッセージ、選択結果など。

```text
id
session_id
sender_type
speaker_name
message_text
message_type
metadata_json
created_at
updated_at
deleted_at
```

`sender_type` 例:

```text
user
character
gm
system
proxy_player
```

`message_type` 例:

```text
dialogue
narration
choice_result
dice_result
system
```

### story_roll_log

サイコロ履歴。

```text
id
session_id
message_id
formula
dice_json
modifier
total
target
outcome
reason
metadata_json
created_at
```

保存例:

```json
{
  "formula": "1d20+3",
  "dice": [
    { "sides": 20, "result": 14 }
  ],
  "modifier": 3,
  "total": 17,
  "target": 12,
  "outcome": "success",
  "reason": "罠を調べる"
}
```

### story_image

セッション中に生成・表示した画像。

既存の `asset` を参照する。

```text
id
session_id
asset_id
source_message_id
visual_type
subject
prompt_text
reference_asset_ids_json
metadata_json
created_at
```

`visual_type` 例:

```text
character
location
item
monster
romance_event
combat
```

役割:

- 画像生成履歴を保持する
- どのメッセージや場面から生成されたかを追跡する
- 画風基準画像やキャラ基準画像との関係を保持する

### 後で追加を検討するテーブル

初期実装ではJSONに寄せるが、管理画面や検索が必要になったら分離する。

```text
story_event_definition
story_item_definition
story_choice_log
story_state_history
```

候補の役割:

- `story_event_definition`: イベントデッキを個別管理する
- `story_item_definition`: アイテム定義を個別管理する
- `story_choice_log`: 選択肢の提示と選択履歴を追跡する
- `story_state_history`: 状態更新履歴を保存し、巻き戻しやデバッグに使う

### 既存テーブルとの関係

旧:

```text
live_chat_room
chat_session
session_state
chat_message
session_image
```

新:

```text
story
story_session
story_session_state
story_message
story_image
story_roll_log
```

旧テーブルは残す。

新UIは新テーブルを見る。

既存コードは参考にして移植する。

## 20. 実装方針

推奨は、新しい `story` / `story_session` 系を作り、既存ライブチャットを参考に移植する案。

理由:

- 概念がきれいになる
- UIとコードの責務が一致する
- TRPG、恋愛攻略、イベント、サイコロ、画風基準を拡張しやすい
- 旧ライブチャットを戻し先として残せる

既存コードは削除せず、まず並行実装する。

### MVP範囲

初期実装では、以下をMVPとして作る。

- `story`
- `story_session`
- `story_session_state`
- `story_message`
- ストーリー一覧 / 編集
- Markdown設定保存
- Markdown設定のAI解析
- `config_json` 保存
- セッション開始
- セッション画面
- directionAI / GM 簡易版
- state_patch生成
- state_patch検証・適用
- 3択
- セリフ自動生成
- 関係性による選択肢変化
- キャラクターの気まぐれ行動
- 失敗してもおいしい展開
- メール連動の下地

初期実装で後回しにするもの:

- 画像生成
- 画風基準画像
- シーン画像生成
- 画像内伏線

ただし、画像生成を後で入れやすいように、状態設計とテーブル設計には `visual_state`、`story_image`、`style_reference_asset_id` を最初から入れておく。

### URL方針

新UIは以下のURLを基本にする。

```text
/projects/<project_id>/stories
/projects/<project_id>/stories/new
/projects/<project_id>/stories/<story_id>/edit
/projects/<project_id>/story-sessions
/projects/<project_id>/story-sessions/<session_id>
```

旧ライブチャットUIはすぐには削除せず、新UIが動くまでは残す。

新UIが動いたら、メニューから旧ルーム / 旧ライブチャットを隠す。

## 21. 面白さ要件

TRPG化では、単に状態管理や選択肢を追加するだけではなく、ユーザーが驚き、迷い、キャラクターに感情移入できる展開を作る。

### マスト要件

以下は初期から重視する。

#### キャラクターの気まぐれ行動

ユーザーが選ぶだけでなく、キャラクター側も意思を持って動く。

例:

- ノアが勝手に扉を閉める
- ノアが嘘をつく
- ノアが手を引いて別ルートへ進む
- ノアが危険を察して、ユーザーの選択を止める
- ノアが秘密を隠すために話題を逸らす

これにより、キャラクターが単なる応答装置ではなく、セッション内の相棒として感じられるようにする。

#### 関係性による選択肢変化

親密度、信頼度、緊張度によって選択肢の内容を変える。

親密度が低い場合:

```text
ノアに確認する
距離を取る
自分で調べる
```

親密度が高い場合:

```text
手を取って進む
耳元で問いかける
ノアをかばう
```

選択肢は、現在の関係性を反映して変化する。

#### メール連動

セッション中に起きたことを、後から届くメールに反映する。

例:

- さっき手を取ってくれたこと、まだ覚えています
- あの剣、あなたが渡してくれたから持てた気がします
- 本当は、あの部屋で少し怖かったんです

メールは単なるランダム生成ではなく、セッションの余韻として使う。

#### 失敗してもおいしい

サイコロ失敗や危険選択を、単なる罰にしない。

例:

- 罠にかかったが、ノアと密着する
- 逃走失敗したが、秘密の部屋に落ちる
- 説得失敗したが、ノアの本音が少し漏れる
- 戦闘に失敗したが、ノアがかばって関係性が変化する

失敗しても物語が進み、恋愛、秘密、謎、危険のいずれかが深まるようにする。

### 追加で入れたい要素

実現可能であれば、以下も順次入れる。

#### 秘密メーター

キャラクターが隠している秘密を少しずつ暴く。

```text
ノアの秘密: 23%
```

見つめる、問い詰める、危険な選択をする、特定アイテムを使うことで進行する。

#### 緊張度

好感度だけでなく、緊張度を持たせる。

- 親密度: 好意
- 信頼度: 安心
- 緊張度: ドキドキ、危うさ、艶っぽさ

恋愛描写や艶っぽい場面は、親密度だけでなく緊張度も参照する。

#### 成功しても代償

成功しても、必ずしも完全な得だけにしない。

例:

- 宝箱は開いたが危険度が上がる
- モンスターから逃げたがノアとはぐれる
- 秘密を聞けたがノアが少し傷つく

#### 未解決スレッド

常に2〜3個の未解決の謎や伏線を保持する。

例:

- 奥の扉の歌声
- ノアが知っているはずのない名前
- 銀の剣が反応する理由

directionAIは、会話が淡々としてきたら未解決スレッドを再利用して展開を動かす。

#### イベント予兆

事件を突然起こすだけでなく、事前に小さな違和感を出す。

例:

- 壁の文字が一瞬だけ変わる
- ノアが聞こえない声に反応する
- 持っている剣が熱を帯びる

#### 画像の伏線

画像生成を実装した後、画像内に小さな違和感や伏線を入れる。

例:

- 背景の鏡に別のノアが映る
- 宝箱の紋章が前の部屋と同じ
- ノアの影だけ剣を持っていない

これは画像生成実装後の拡張とする。

## 22. 段階的な進め方

1. 設計書を固める
2. URL、モデル名、サービス名を決める
3. `story` / `story_session` モデルを作る
4. ストーリー一覧 / 編集画面を作る
5. Markdown解析とJSON保存を作る
6. セッション一覧 / 開始画面を作る
7. セッション画面を既存ライブチャットから移植する
8. directionAI / GMを作る
9. state_patchの検証・適用処理を作る
10. セリフ自動生成をGM裁定後に動かす
11. 3択と状態更新を実装する
12. アイテム、装備、見える所持品を実装する
13. サイコロを実装する
14. イベントデッキを実装する
15. シーン画像と画風基準画像を実装する
16. 恋愛段階制御を実装する
17. UIから旧ルーム / 旧ライブチャット表示を隠す

## 23. 未決事項

- 旧ライブチャットをどの時点でUIから完全に隠すか
- 既存のルーム / セッションデータを移行するか
- メールを新セッションへどう紐づけるか
- Feed内容をストーリーへ直接反映するか、キャラクター経由のままにするか
- イベントデッキをどこまで管理画面で編集可能にするか
- サイコロ結果を常に表示するか、ストーリーごとに切り替えるか
- 恋愛 / 艶っぽさの強度上限をどの粒度で設定するか
