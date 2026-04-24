# ライブ会話 キャラクター記憶仕様書

## 1. 目的
- ライブ会話でキャラクターが話した内容から、好み・価値観・恋愛傾向を継続的に記憶できるようにする。
- プレイヤーがその記憶に沿った会話や贈り物をした場合、評価を上げる。
- 逆に、嫌いなもの・苦手な話題・恋愛的な地雷を踏んだ場合、評価を下げる。
- 記憶した内容はセッション内だけでなく、キャラクター設定にも反映し、次回以降の会話でも使えるようにする。

## 2. 基本方針
- キャラクター記憶は「永続記憶」と「セッション記憶」の2層で管理する。
- 永続記憶は `character` に保存し、キャラクター固有の設定として扱う。
- セッション記憶は `session_state.state_json.session_memory` に保存し、今回の会話で新しく分かった情報や印象イベントを保持する。
- セッション終了後も有用な情報は永続記憶へ同期する。

## 3. 記憶カテゴリ
### 3-1. 基本嗜好
- `likes`
  - 好きなもの、好物、嬉しい贈り物
- `dislikes`
  - 嫌いなもの、避けたいもの
- `hobbies`
  - 趣味、普段よくやること、好きな過ごし方
- `weak_points`
  - 弱いツボ、刺さる言動

### 3-2. 会話・接し方の相性
- `speech_preferences`
  - 話しかけ方の好み
- `taboos`
  - 会話で踏んではいけない地雷
- `trust_conditions`
  - 信頼が上がる条件
- `relationship_triggers`
  - 距離が縮むきっかけ

### 3-3. 恋愛記憶
- `romance_preferences`
  - 恋愛傾向のまとまり
- `romance_preferences.attraction_points`
  - 惹かれる相手・態度
- `romance_preferences.favorite_approach`
  - 好きな距離の詰め方
- `romance_preferences.avoid_approach`
  - 苦手な迫り方
- `romance_preferences.romance_pace`
  - 恋愛進行の好み
- `romance_preferences.boundaries`
  - 境界線、嫌がる踏み込み

### 3-4. 動的記憶
- `memorable_events`
  - 印象に残った出来事
- `current_interests`
  - 最近興味を示したこと
- `current_mood_bias`
  - 今の気分補正

## 4. データ構造
### 4-1. `character` 永続記憶
- `memory_notes: TEXT`
- `favorite_items_json: TEXT`
- 将来的に `memory_profile_json: TEXT` を追加する

### 4-2. `memory_profile_json` 想定構造
```json
{
  "likes": ["辛いもの", "夜景"],
  "dislikes": ["騒音", "甘すぎるお菓子"],
  "hobbies": ["読書", "散歩"],
  "weak_points": ["名前を優しく呼ばれる"],
  "speech_preferences": ["丁寧に話されると心地いい"],
  "taboos": ["過去の失敗を茶化されること"],
  "trust_conditions": ["約束を守る", "話を最後まで聞く"],
  "relationship_triggers": ["共通の趣味があると距離が縮まる"],
  "romance_preferences": {
    "attraction_points": ["知的な会話", "余裕のある態度"],
    "favorite_approach": ["自然に距離を縮める"],
    "avoid_approach": ["命令口調", "下品な冗談"],
    "romance_pace": ["ゆっくり"],
    "boundaries": ["初対面で重すぎる告白は苦手"]
  },
  "gift_preferences": {
    "positive": ["辛い調味料", "綺麗な小物"],
    "negative": ["安っぽい冗談グッズ"]
  },
  "updated_at": "2026-04-25T12:00:00"
}
```

### 4-3. `session_memory.character_memories` 想定構造
```json
{
  "ノア": {
    "likes": ["夜景"],
    "dislikes": ["騒がしい場所"],
    "hobbies": ["散歩"],
    "weak_points": ["気遣われると弱い"],
    "taboos": ["過去を詮索されること"],
    "romance_preferences": {
      "favorite_approach": ["静かに寄り添う"],
      "avoid_approach": ["強引すぎる距離の詰め方"]
    },
    "memorable_events": ["プレイヤーが夜景の話を覚えていた"]
  }
}
```

## 5. AI抽出ルール
- キャラクターの発話を優先して抽出する。
- 断定的な好みは永続候補、軽い一回発言は `memorable_events` に留める。
- 同義語は後段で正規化する。
- 抽出タイミングは返答生成後、`session_memory` 更新時、評価更新時とする。

## 6. 評価ルール
### 6-1. 加点
- `likes` に合う話題: +4
- `hobbies` が一致する会話: +6
- `trust_conditions` を満たす行動: +5
- `relationship_triggers` に当たる接し方: +8
- `romance_preferences.favorite_approach` に沿う接近: +10
- `gift_preferences.positive` に合う贈り物: +12

### 6-2. 減点
- `dislikes` に触れる: -5
- `taboos` を踏む: -10
- `romance_preferences.avoid_approach` に該当: -10
- `romance_preferences.boundaries` を越える: -15
- `gift_preferences.negative` に合う贈り物: -8

## 7. AI返答への反映
- 記憶済みの好き嫌いを忘れない。
- 好物や趣味に触れられたら反応を変える。
- 地雷を踏まれたら感情トーンを変える。
- 恋愛嗜好に刺さる接し方なら距離感を柔らかくする。

## 8. UI仕様
### 8-1. キャラクター編集画面
- 好きなもの
- 嫌いなもの
- 趣味
- 苦手なこと・話題
- 恋愛傾向
- 会話メモ

### 8-2. ライブ会話画面
- セッション設定アコーディオン配下に `会話メモ` を表示
- キャラクターごとにカテゴリ表示する
- 最近分かった好み、地雷、恋愛的に刺さる接し方、印象イベントを見せる

## 9. 実装ステップ案
### Phase 1
- `memory_profile_json` を追加
- `likes / dislikes / hobbies / taboos` を構造化

### Phase 2
- 評価ロジックへ加点・減点を追加
- `memorable_events` を返答生成に反映

### Phase 3
- `romance_preferences` を追加
- 会話返答と評価に恋愛傾向を反映

### Phase 4
- 贈り物機能実装
- `gift_preferences` と評価連動

## 10. v1でまず入れる範囲
- `likes`
- `dislikes`
- `hobbies`
- `taboos`
- `romance_preferences.favorite_approach`
- `romance_preferences.avoid_approach`
- `memorable_events`

## 11. 非対象
- 露骨な性的描写そのものの保存
- 画像生成用の直接的な性的指示
- キャラクターごとの詳細分岐シナリオ管理
