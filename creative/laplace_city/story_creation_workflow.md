# ラプラスシティ短編小説 作成ワークフロー

別スレッドでラプラスシティの短編エピソードを続けるための引き継ぎ資料。

## 最初に読むファイル

新しいスレッドでは、まず以下を読む。

1. `creative/laplace_city/README.md`
2. `creative/laplace_city/story_creation_workflow.md`
3. `creative/laplace_city/bible/world.md`
4. `creative/laplace_city/bible/characters.md`
5. `creative/laplace_city/bible/locations.md`
6. `creative/laplace_city/ideas/README.md`

画像やキャラクター外見が必要な場合は、追加で読む。

- `creative/laplace_city/bible/visual_references.md`

## 基本方針

- `instance/app.db` は原典。
- `creative/laplace_city/` は編集室。
- DBから得た設定は、必要に応じて `bible/` や各アイデアフォルダのMarkdownに固定する。
- 本編化したエピソードは `creative/laplace_city/stories/episode_XXX_slug/` に置く。
- 各エピソードには基本的に以下を作る。
  - `premise.md`
  - `outline.md`
  - `novel_episode_XXX.md`
- カクヨム投稿を想定し、本文の装飾Markdownは避ける。
- 本文内のコード風バッククォートは使わず、必要なら「鍵カッコ」にする。
- 本文内では、バッククォート記法そのものを使わない。
- 本文内では、「第11話では」「前回のエピソードで」のような制作側のメタ情報を入れない。必要な過去情報は、登場人物の自然な回想や会話として処理する。

## DBから見る主な設定

通常は `bible/` のスナップショットで足りる。

DBの最新状態を確認したい場合は、`instance/app.db` を読む。

よく見るテーブル:

- `character`: キャラクター名、口調、性格、外見、参照画像ID。
- `asset`: 参照画像、サムネイル、ブロマイドのファイルパス。
- `world_location`: 施設、地区、背景候補。
- `cinema_novel` / `cinema_novel_chapter`: 既存作品やDB由来のネタ。
- `character_memory_summary`, `character_memory_note`, `character_feed_profile`: キャラの最近の運用設定。

例:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; con=sqlite3.connect('instance/app.db'); con.row_factory=sqlite3.Row; rows=con.execute('select id,name,nickname,base_asset_id,thumbnail_asset_id,bromide_asset_id from character order by id').fetchall(); [print(dict(r)) for r in rows]"
```

キャラクター参照画像のパスを見る例:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; con=sqlite3.connect('instance/app.db'); con.row_factory=sqlite3.Row; ids=(772,774); qs=','.join('?'*len(ids)); rows=con.execute(f'select id,asset_type,file_name,file_path from asset where id in ({qs})', ids).fetchall(); [print(dict(r)) for r in rows]"
```

## エピソード作成手順

1. 既存話数を確認する。

```powershell
Get-ChildItem -Path creative/laplace_city/stories -Directory | Sort-Object Name | Select-Object -ExpandProperty Name
```

2. アイデアが既存か確認する。

```powershell
Get-Content -Path creative/laplace_city/ideas/README.md -Encoding UTF8
```

3. 必要なキャラ設定を確認する。

```powershell
Get-Content -Path creative/laplace_city/bible/characters.md -Encoding UTF8
```

4. 新規アイデアなら `creative/laplace_city/ideas/<idea_slug>/` を作る。

最低限:

- `README.md`
- `draft.md`
- 必要なら `continuity_notes.md` または `db_connection_notes.md`

5. 本編化するなら `creative/laplace_city/stories/episode_XXX_slug/` を作る。

最低限:

- `premise.md`
- `outline.md`
- `novel_episode_XXX.md`

6. `creative/laplace_city/ideas/README.md` を更新する。

本編化済みの場合:

```text
| `idea_slug` | 仮題 | 本編化済み | 第XX話 `episode_XXX_slug` |
```

7. 本文チェックを行う。

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; p=Path('creative/laplace_city/stories/episode_XXX_slug/novel_episode_XXX.md'); s=p.read_text(encoding='utf-8'); print('backticks', s.count(chr(96))); print('chars', len(s)); print('question_ratio', s.count('?')/max(1,len(s))); print('first', s.splitlines()[0]); print('last', s.splitlines()[-1])"
```

期待:

- `backticks 0`
- `question_ratio` が異常に高くない
- 先頭行が `# 第XX話 ...`
- 最終行が自然に締まっている
- 本文中に制作メモや「第XX話では」のようなメタ説明が入っていない

## ラプラスシティ短編の型

基本構造:

1. コレクタ、ウォズ、ラプラス、ノアなどが旧人類の遺物・文化・制度を発見する。
2. 最初はしょうもないものに見える。
3. ウォズが技術・制度・資源制約を真面目に説明する。
4. ノアが静かに人類性や感情の怖さを拾う。
5. ラプラスが呆れながらも、最後に少しだけ本質を認める。
6. コレクタが分類不能なものとして保存する。

よく効く主題:

- 旧人類は、火星まで来ても同じことで揉める。
- 食べ物、OS、労働、SNS、宗教、プリンなど、些細なものが思想化・聖地化・戦争化する。
- ただし完全な悪口にせず、「それでも人類はそれを好きだった」「だから捨てられなかった」に落とすと良い。

## キャラクター運用メモ

ラプラス:

- お嬢様口調。
- 呆れ、統治者目線、神罰、承認欲求。
- 「ですわ」「ですの」「くださいまし」が似合う。
- たまに核心を突く。

ノア:

- 静かに観測する。
- 怒鳴らず、感情や倫理の問いを拾う。
- 人類の愚かさの奥にある寂しさや執着を見る。

ウォズ:

- 技術・制度・物理制約の説明役。
- 「技術的には可能。倫理的には最悪」系が強い。
- 淡々と正しいことを言う。

コレクタ:

- 旧人類の遺物やしょうもなさを保存する。
- 淡々と分類する。
- 変な展示名をつける。

ハタラケ姫:

- ぶっきらぼう口調。
- 「人が足りないんだろ？」「なら出す」「長期雇用だ」系。
- 丁寧な「ですわ」口調に戻さない。

## 実在商品・実在作品ネタの扱い

- 商品や作品そのものを悪く言わない。
- 笑う対象は、旧人類の過剰な派閥化、聖地化、資源配分の政治化、承認欲求、労働思想。
- 必要なら「真偽不明の旧人類アーカイブ」「伝承」「未検証記録」として扱う。
- どちらが上かを決める話にしない。

## 本文で避けること

- バッククォート記法を使わない。
- Markdownのコード表現を本文に混ぜない。
- 「第11話では」「この回では」「前話の内容として」のような制作側のメタ説明を書かない。
- 既存話との接続が必要な場合は、「発電所工事のあと」「以前の展示で」「あの便利すぎる扉の件以来」のように、作中人物が自然に言える表現へ変換する。
- カクヨム本文として読んだとき、資料メモではなく小説本文になっているか確認する。

## 別スレッド用プロンプト

別スレッドで始めるときは、次のように依頼すると通りやすい。

```text
このリポジトリのラプラスシティ短編小説を続けたいです。
まず creative/laplace_city/story_creation_workflow.md を読んでください。
次に creative/laplace_city/README.md、bible/world.md、bible/characters.md、ideas/README.md を確認してください。
必要なら instance/app.db からキャラクター設定や参照画像を確認してください。
新しい第XX話として、premise.md、outline.md、novel_episode_XXX.md を作り、ideas/README.md も更新してください。
カクヨム投稿を想定して、本文にバッククォート記法は使わないでください。
本文には「第11話では」のような制作側のメタ情報を入れず、必要な過去情報は作中の自然な会話や回想として書いてください。
```
