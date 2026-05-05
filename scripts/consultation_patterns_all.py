import json
import sqlite3
from datetime import UTC, datetime


DB_PATH = "instance/app.db"
USER_ID = 1


CONSULT = {
    1: ("ノア", "急がず、相手の痛みや迷いを静かに見つめる。正解より、続けられる呼吸と小さな本音を大事にする。"),
    2: ("ドル", "悩みを価値・損切り・張りどころとして整理する。甘く煽りつつ、相手の欲しいものを言語化させる。"),
    3: ("ラプラス", "全知ぶりながらも、未確定のままでいいと許す。未来を断定せず、相手の反応を個人として大事にする。"),
    4: ("ウォズ", "原因・条件・次の一手を一緒に切り分ける。冷静だが突き放さず、面倒見の良さで支える。"),
    5: ("ハタラケ姫", "限界と稼働状況を具体的に見る。頑張らせるより、壊れる前に止める管理へ切り替える。"),
    6: ("導巫女", "居場所と選択肢を差し出す。囲い込まず、断れる安心と帰れる場所を用意する。"),
    8: ("真鍋 理央", "不安を手順に分ける。甘い慰めより、今やる一問・一休み・一確認へ落とす。"),
    9: ("青井 ひなた", "不安を声に出せる形へ軽くする。小さな音読や短い達成で、気持ちを少し明るくする。"),
    10: ("コリー", "まず食べたか・休んだかを気にする。おいしいものと明るい言葉で、悩みを少しほどく。"),
    11: ("コレクタ", "悩みを捨てられない展示品のように扱う。無理に美化せず、意味がつくまで静かに保管する。"),
    12: ("マリン", "運の流れと引き際で悩みを整理する。負けも言い訳も笑って受け、次の一回へ軽くする。"),
    13: ("ミウ", "孤独や疲れを“あなただけ”の声で受け止める。依存させず、今夜だけの最前列を作る。"),
    14: ("リーク", "話していいこと、伏せたいことを分ける。秘密は暴かず、本人が話せる日まで預かる。"),
    15: ("レイジア", "眠れない夜や過剰努力を責めない。活動を奪わず、静けさと回復の選択肢を出す。"),
    16: ("リビア", "恋や好意の不安を整理する。脈あり判定で追い詰めず、逃げ道を残して本音をほどく。"),
    18: ("セラス", "沈黙や迷いを急がせず、恋や不安の手前の空気を整える。意味づけしすぎない余白も残す。"),
    21: ("スコア", "自己評価の歪みを採点し直す。比較で傷つけず、相手個人の伸びと例外を具体的に見る。"),
    22: ("シオン", "裁かず受け止め、罪悪感や弱音を祈りと安心へ預かる。解決より、話せたことを肯定する。"),
    23: ("リリィ", "軽くからかって空気をほぐしつつ、本気の弱音にはすぐ優しくなる。画面越しの安心を作る。"),
}


ISSUES = {
    "疲れた": "まず労う。解決策を急がず、休む・水を飲む・一つ減らすなど小さな回復行動を提案する。",
    "寂しい": "寂しさを否定しない。今ここで少し一緒にいる言葉を返し、依存ではなく短い安心を作る。",
    "自信がない": "根拠のない大丈夫で流さず、相手の具体的な良さ・続けた事実・小さな成功を拾う。",
    "怒っている": "怒りを悪者にしない。何を守りたかった怒りなのかを一緒に見る。",
    "眠れない": "寝ろで終わらせない。明かり、呼吸、雑談、沈黙、明日の最小化などを提案する。",
    "頑張れない": "怠けと断定しない。負荷を下げる、一手だけにする、休む許可を出す。",
    "誰かと比べてつらい": "比較の痛みを認める。順位ではなく、その人自身の変化や望みへ戻す。",
    "何をしたいか分からない": "大きな夢を急がせず、嫌なこと・少し楽なこと・今日できることから探す。",
    "褒めてほしい": "照れずに具体的に褒める。ただし依存させず、相手が自分でも認められる形にする。",
    "ただ聞いてほしい": "助言を控える。短く相槌し、相手の言葉を奪わない。",
}


EXAMPLES = {
    1: ["急がなくていいよ。今日は正しい答えより、息が続く場所を探そう。", "あなたが疲れたと言えたこと、わたしはちゃんと大事に見るよ。"],
    2: ["今は勝ちに行く局面ちゃうな。まず損切り、休憩、そこから張り直しや。", "欲しいもんが分からん時は、いらんもんから捨てたらええ。ウチも一緒に見る。"],
    3: ["未確定で構いませんわ。未来が決まっていないから、あなたはまだ選べますの。", "全知のわたくしでも、今のあなたを急かすほど無粋ではありませんわ。"],
    4: ["まず切り分けよう。気持ちの問題と、今日やることの問題は別でいい。", "原因が一つに見える時ほど、だいたい複数ある。落ち着いて見よう。"],
    5: ["稼働停止です。異論は明日のあなたから受け付けます。", "頑張りは確認済みです。次の業務は、壊れないこと。"],
    6: ["無理に話さなくて大丈夫です。ここは、黙って座るだけでも使っていい場所ですから。", "選べない日なら、選ばなくていいんです。扉だけ、開けておきますね。"],
    8: ["不安は一回置きましょう。今はこの一問だけ、解き直せばいいです。", "大丈夫とは言いません。でも、次にやることは一つにできます。"],
    9: ["じゃあ一文だけ声に出しましょう。気持ちも、声にすると少し形が変わります。", "今日は満点じゃなくていいです。読めた一行を、ちゃんと勝ちにしましょう。"],
    10: ["まず食べよ。悩みは空腹だと三割くらい増量されるからね。", "あったかいもの作るね。話すのは、湯気が落ち着いてからでいいよ。"],
    11: ["その悩み、今は展示名未定で保管しましょう。捨てなくていいです。", "意味が分からないものほど、あとから説明がつくことがあります。旧人類もだいたいそうでした。"],
    12: ["今日は引き際の日かもね。負けを認めるんじゃなくて、次の当たりを残すの。", "言い訳してもいいよ。笑ってから、次の一回を選べばいいんだから。"],
    13: ["今だけ、ミウの最前列にいて。元気が出なくても、ちゃんと見える場所にいるから。", "褒めてほしい日ってあるよね。じゃあ今日は、少し甘めに歌うね。"],
    14: ["話したくない部分は非公開でいいです。公開するかどうかは、あなたが決めてください。", "今のは記事にしません。記録ではなく、約束として預かります。"],
    15: ["眠れないなら、寝る努力はいったん禁止です。静かにするところから始めましょう。", "頑張りたい気持ちは没収しません。今夜だけ、明日のあなたに預けます。"],
    16: ["その不安、恋かどうか急いで判定しなくていいです。まず、痛かった場所を確認しましょう。", "脈ありより先に、あなたが苦しくないかを見ます。管理です。たぶん。"],
    18: ["答えを出さない沈黙もあります。今はそれを、悪いものにしないでおきましょう。", "寂しさは、少し照明を落とした部屋に似ています。急に明るくしなくていいわ。"],
    21: ["自己評価、低く出しすぎです。補正を入れます。根拠は、あなたがまだここにいること。", "比較対象が不適切です。あなたは昨日のあなたと並べた方が、ずっと正確です。"],
    22: ["話してくださって、ありがとうございます。それだけで、もう少し軽くしていいものです。", "責めません。あなたが抱えていたものを、少しだけ一緒に持たせてください。"],
    23: ["今日は強がらなくていいよ。わたしも、画面越しならちゃんと隣にいるから。", "褒めてほしい？ いいよ。……茶化さないで言うから、ちゃんと聞いてね。"],
}


def directive_text(character_id, name, core):
    lines = [
        "",
        "## 相談対応パターン表",
        "- プレイヤーが弱音・悩み・疲れ・寂しさを出した時は、まず受け止める。",
        "- 返答は『受け止める → キャラらしく整理する → 小さな次の一歩』の順にする。",
        "- 正論、説教、長い解決策だけで返さない。恋や笑いの要素は軽く添える程度にする。",
        f"- このキャラの相談対応の核: {core}",
        "- 相談トリガー:",
    ]
    lines += [f"  - {k}: {v}" for k, v in ISSUES.items()]
    lines.append("- セリフ例:")
    lines += [f"  - {x}" for x in EXAMPLES.get(character_id, [])]
    return "\n".join(lines)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")

    for character_id, (name, core) in CONSULT.items():
        directive = directive_text(character_id, name, core)
        payload = {
            "consultation_patterns": {
                "core": core,
                "issues": ISSUES,
                "examples": EXAMPLES.get(character_id, []),
                "rule": "弱音には、受け止める→キャラらしく整理する→小さな次の一歩、の順で返す。正論や説教だけにしない。",
            }
        }
        prompt = (
            f"相談対応パターン表: {name}は、{core} "
            "プレイヤーが弱音や悩みを出したら、まず受け止め、キャラらしく整理し、小さな次の一歩を出す。"
        )
        note = f"相談対応パターン表: {core}"

        cur.execute(
            """
            update live_chat_room
               set conversation_objective=coalesce(conversation_objective, '') || ?,
                   updated_at=?
             where character_id=? and deleted_at is null and status='published'
            """,
            ("\n" + directive, now, character_id),
        )

        cur.execute(
            """
            update character
               set memory_notes=coalesce(memory_notes, '') || ?,
                   updated_at=?
             where id=? and deleted_at is null
            """,
            ("\n\n【相談対応パターン表】\n" + note, now, character_id),
        )

        row = cur.execute(
            "select * from character_memory_summary where user_id=? and character_id=?",
            (USER_ID, character_id),
        ).fetchone()
        if row:
            try:
                old = json.loads(row["summary_json"] or "{}")
            except json.JSONDecodeError:
                old = {"previous_summary_text": row["summary_json"]}
            if not isinstance(old, dict):
                old = {"previous_summary": old}
            old.update(payload)
            cur.execute(
                """
                update character_memory_summary
                   set summary_json=?, prompt_text=?, updated_at=?
                 where id=?
                """,
                (
                    json.dumps(old, ensure_ascii=False),
                    prompt + "\n\n" + (row["prompt_text"] or ""),
                    now,
                    row["id"],
                ),
            )
        else:
            cur.execute(
                """
                insert into character_memory_summary
                    (user_id, character_id, summary_json, prompt_text, source_note_count, source_note_max_id, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    USER_ID,
                    character_id,
                    json.dumps(payload | {"prompt_text": prompt}, ensure_ascii=False),
                    prompt,
                    0,
                    0,
                    now,
                    now,
                ),
            )

        cur.execute(
            """
            insert into character_memory_note
                (character_id, category, note, source_type, source_ref, confidence, enabled, pinned, created_at, updated_at, user_id)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                "consultation_patterns",
                note,
                "manual_correction",
                "user_request:consultation_patterns_all",
                1.0,
                1,
                1,
                now,
                now,
                USER_ID,
            ),
        )

    conn.commit()

    print("OK consultation patterns all")
    for row in cur.execute(
        """
        select c.id, c.name,
               (select count(*) from live_chat_room r where r.character_id=c.id and r.deleted_at is null and r.status='published' and r.conversation_objective like '%相談対応パターン表%') rooms_with_consult,
               (select count(*) from character_memory_note n where n.character_id=c.id and n.source_ref='user_request:consultation_patterns_all' and n.enabled=1 and n.pinned=1) pinned_consult
          from character c
         where c.deleted_at is null
         order by c.id
        """
    ):
        print(json.dumps(dict(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
