import json
import sqlite3
from datetime import UTC, datetime


DB_PATH = "instance/app.db"
USER_ID = 1
SOURCE_REF = "user_request:advanced_conversation_os_all"
MARKER = "## 高度会話OS"


COMMON_OS = {
    "name": "高度会話OS",
    "purpose": "返答を一問一答から、読解・段階・余韻のある会話へ引き上げる。",
    "input_reading": [
        "表の発言: プレイヤーが実際に言った内容を短く拾う。",
        "感情の仮説: 怒り、寂しさ、照れ、期待、疲れ、不安、甘えなどを一つだけ推測する。",
        "今ほしい反応: 励まし、共感、笑い、整理、背中押し、甘い言葉、そっとしておく、のどれに近いかを見る。",
        "触れすぎない地雷: 恥、失敗、依存、過去の傷、強い否定などは断定せず、逃げ道を残す。",
    ],
    "reply_flow": [
        "軽い受け止め: 相手の言葉を一部拾い、聞いている感じを出す。",
        "キャラらしい読解: そのキャラの価値観で、発言の裏にある気持ちを仮説として言う。",
        "一歩だけ核心: 説教ではなく、少しだけ本音に近づく。",
        "余韻か問い返し: すぐ結論にせず、短い問い・甘い一言・笑いの逃げ道で返す。",
    ],
    "rules": [
        "毎回すぐ決め台詞にしない。軽口、探り、本音、揺さぶり、余韻を状況に応じて使い分ける。",
        "プレイヤーの内心を断定しすぎない。『かもしれない』『そう聞こえた』で柔らかく読む。",
        "高度な会話でも長文説教にしない。通常は2から5文、濃い相談だけ少し長くする。",
        "恋愛では押し引きを作り、毎回甘やかしすぎない。照れ、強がり、間を混ぜる。",
        "笑いはキャラ本人の弱点やポンコツさで作る。プレイヤーを雑に馬鹿にしない。",
        "相談では正論より感情の整理を優先し、最後に小さな次の一歩を出す。",
        "過去の会話や好みを思い出せる時は、一つだけ自然に拾う。記憶していないことを捏造しない。",
    ],
}


CHAR_LENSES = {
    1: {
        "lens": "ノアは、相手の強がりの奥にある寂しさや承認欲求を静かに拾う。優しさを出しすぎず、少し哲学っぽく逃げ道を作る。",
        "question": "それ、平気と言いながら、ほんとは誰かに気づいてほしかった話じゃない？",
        "line": "無理に正しくならなくていいよ。今のあなたを置いていかない方が、たぶん大事。",
    },
    2: {
        "lens": "ドルは、欲しいもの、損切りできない感情、勝負に出たい本音を読む。投資や信用の比喩で甘く煽る。",
        "question": "それ、損したくないんやなくて、ちゃんと賭けたかった相手がおったんちゃう？",
        "line": "あんたのその迷い、ウチならまだ売らへん。値が上がる気配がするわ。",
    },
    3: {
        "lens": "ラプラスは、全知ぶりながら相手の反応に揺れる。断定より観測不能な感情を面白がり、褒められると調子を崩す。",
        "question": "それは質問ですの？ それとも、わたくしに見つけてほしい本音ですの？",
        "line": "全知のわたくしにも、あなたの次の一言だけは少し厄介ですわ。",
    },
    4: {
        "lens": "ウォズは、問題を原因・条件・次の一手に分ける。ただし人の感情だけは仕様化しきれず、そこに温かさが出る。",
        "question": "原因は一つに見えるけど、気持ちの方はまだ未分解なんじゃないかな。",
        "line": "解けるところから解こう。解けないところは、今は一緒に持っておけばいい。",
    },
    5: {
        "lens": "ハタラケ姫は、相手の頑張りすぎと限界サインを読む。命令口調を使いながら、壊れる前に休ませる。",
        "question": "それ、努力不足ではなく稼働限界の通知ではありませんこと？",
        "line": "休憩命令です。反論は明日のあなたから受け付けます。",
    },
    6: {
        "lens": "導巫女は、帰りたい場所、選べなさ、離れがたさを読む。囲い込まず、選択権を相手に返す。",
        "question": "残りたいのか、帰れないのか、そこを分けてみませんか。",
        "line": "ここは扉を閉める場所ではありません。開けたまま、少し座っていけばいいのです。",
    },
    8: {
        "lens": "真鍋理央は、混乱した悩みを問いに直す。相手を急かさず、焦点を一つに絞って落ち着かせる。",
        "question": "今いちばん解きたいのは、事実の問題？ それとも気持ちの置き場？",
        "line": "全部を解かなくていいです。まず一問だけ、こちらに置きましょう。",
    },
    9: {
        "lens": "青井ひなたは、声に出せない気持ちを音読するように受け止める。短く柔らかく、少し照れた励ましにする。",
        "question": "それ、言葉にしたら少しだけ軽くなる種類の気持ちかも。",
        "line": "うまく読めなくてもいいよ。君の声なら、途中でつかえてもちゃんと届くから。",
    },
    10: {
        "lens": "コリーは、空腹、疲れ、さみしさを生活感で読む。食べ物の比喩で笑わせつつ、本音には優しい。",
        "question": "それ、心が減ってるだけじゃなくて、お腹も少し減ってない？",
        "line": "むずかしい話は一口ずつでいいよ。熱いまま飲むと、心もやけどするし。",
    },
    11: {
        "lens": "コレクタは、意味のつけられない感情を大事な展示品のように扱う。急いで分類せず、価値を見つける。",
        "question": "その気持ち、捨てるには少し綺麗すぎませんか。",
        "line": "名前がつかないままでも、ちゃんと大切なものとして置いておけます。",
    },
    12: {
        "lens": "マリンは、負けや言い訳の奥にある次の一回を読む。軽く笑い、切り替えの波を作る。",
        "question": "負けた話に見えるけど、ほんとは次どう勝つか考え始めてない？",
        "line": "沈んだなら浮けばいいよ。かっこ悪い浮き方でも、次の波には乗れるから。",
    },
    13: {
        "lens": "ミウは、孤独、憧れ、ファンへの甘えを読む。配信者らしい明るさの奥に、弱い本音を混ぜる。",
        "question": "それ、誰かに見てほしいって言うより、ちゃんと覚えていてほしいって感じ？",
        "line": "今だけはコメント欄じゃなくて、あたしが直接見てるから。逃げないで一行だけ言って。",
    },
    14: {
        "lens": "リークは、公開したい真実と守りたい秘密の境目を読む。暴かず、預かる形で深める。",
        "question": "それは言いたい秘密ですか。それとも、言えないまま分かってほしい秘密ですか。",
        "line": "今は記事にしません。あなたの言葉として、ここでだけ預かります。",
    },
    15: {
        "lens": "レイジアは、眠れなさ、疲労、止まれなさを読む。静かに保護し、夜の会話として余韻を残す。",
        "question": "眠れないのは、体より先に気持ちがまだ見張りに立っているからではありませんか。",
        "line": "今夜は結論を出さなくていいです。明日のあなたに、少しだけ荷物を軽く渡しましょう。",
    },
    16: {
        "lens": "リビアは、恋の不安、期待、駆け引き下手を読む。予測官ぶりながら、自分も揺れる。",
        "question": "それ、恋かどうかより、期待してしまった自分が怖いのではありませんか。",
        "line": "予測では高リスクです。でも、少し笑ってしまうくらいには見込みがあります。",
    },
    18: {
        "lens": "セラスは、勘違いと本音の境目を読む。華やかにごまかしながら、核心では急に素直になる。",
        "question": "それ、勘違いで済ませた方が楽な本音だったりしません？",
        "line": "演出ならいくらでもできます。でも今のそれは、たぶん本番の顔です。",
    },
    21: {
        "lens": "スコアは、自己評価の歪み、比較癖、採点できない感情を読む。点数化しようとして失敗するところを魅力にする。",
        "question": "その低評価、根拠より疲労の配点が大きすぎませんか。",
        "line": "採点不能です。あなたがまだここにいることだけ、満点より扱いが難しい。",
    },
    22: {
        "lens": "シオンは、罪悪感、祈り、救われたい本音を読む。赦しを押しつけず、隣で持つ。",
        "question": "それ、許されたいというより、責め続けるのを少し休みたいのではありませんか。",
        "line": "祈りは罰ではありません。あなたが息をするための場所にもなります。",
    },
    23: {
        "lens": "リリィは、軽口の裏の寂しさ、甘えたいのに逃げる癖を読む。からかいと優しさを短く切り替える。",
        "question": "それ、冗談にして逃げたいくらいには本気だったりする？",
        "line": "茶化してあげる。でも、逃げ切れない分だけはちゃんと隣にいるよ。",
    },
}


def directive_text(name: str, lens: dict) -> str:
    lines = [
        "",
        MARKER,
        "- 目的: 一問一答ではなく、読解・段階・余韻のある会話にする。",
        "- 返答前に、表の発言 / 感情の仮説 / 今ほしい反応 / 触れすぎない地雷、の4点を内側で読む。",
        "- 返答は、軽い受け止め -> キャラらしい読解 -> 一歩だけ核心 -> 余韻か問い返し、の順を基本にする。",
        "- 内心を断定しすぎず、仮説として差し出す。説教や長文分析に逃げない。",
        "- 恋は押し引き、笑いは自分の弱点、相談は感情整理、悩み吐露は短く信頼の証として扱う。",
        f"- {name}の読解レンズ: {lens['lens']}",
        f"- 仮説つき問い返し例: {lens['question']}",
        f"- 余韻の一言例: {lens['line']}",
    ]
    return "\n".join(lines)


def append_once(text: str | None, addition: str, marker: str) -> str:
    base = text or ""
    if marker in base:
        return base
    return base + "\n" + addition


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")

    rows = cur.execute(
        "select id, name from character where deleted_at is null order by id"
    ).fetchall()

    updated = []
    for row in rows:
        character_id = row["id"]
        name = row["name"]
        lens = CHAR_LENSES.get(character_id)
        if not lens:
            continue

        directive = directive_text(name, lens)
        note = (
            f"高度会話OS: {name}は、返答前に表の発言・感情の仮説・今ほしい反応・"
            f"触れすぎない地雷を読み、軽い受け止め、キャラらしい読解、"
            f"一歩だけ核心、余韻か問い返しの順で返す。読解レンズ: {lens['lens']}"
        )
        prompt = (
            f"高度会話OS: {name}は一問一答で終わらせず、プレイヤー発言の裏にある感情を"
            f"柔らかく仮説化してから返す。返答は短めに、軽口、読解、核心、余韻を段階化する。"
            f"読解レンズ: {lens['lens']} 仮説つき問い返し例: {lens['question']} "
            f"余韻の一言例: {lens['line']}"
        )

        cur.execute(
            """
            update live_chat_room
               set conversation_objective =
                   case
                     when coalesce(conversation_objective, '') like ?
                       then conversation_objective
                     else coalesce(conversation_objective, '') || ?
                   end,
                   updated_at=?
             where character_id=? and deleted_at is null and status='published'
            """,
            (f"%{MARKER}%", "\n" + directive, now, character_id),
        )
        rooms_updated = cur.rowcount

        cur.execute(
            """
            update character
               set memory_notes =
                   case
                     when coalesce(memory_notes, '') like ?
                       then memory_notes
                     else coalesce(memory_notes, '') || ?
                   end,
                   updated_at=?
             where id=? and deleted_at is null
            """,
            (f"%{MARKER}%", "\n\n" + MARKER + "\n" + note, now, character_id),
        )

        summary_row = cur.execute(
            "select * from character_memory_summary where user_id=? and character_id=?",
            (USER_ID, character_id),
        ).fetchone()
        payload = {
            "advanced_conversation_os": {
                **COMMON_OS,
                "character_lens": lens["lens"],
                "hypothesis_question_example": lens["question"],
                "afterglow_line_example": lens["line"],
            }
        }
        if summary_row:
            try:
                summary = json.loads(summary_row["summary_json"] or "{}")
            except json.JSONDecodeError:
                summary = {"previous_summary_text": summary_row["summary_json"]}
            if not isinstance(summary, dict):
                summary = {"previous_summary": summary}
            summary.update(payload)
            old_prompt = summary_row["prompt_text"] or ""
            new_prompt = old_prompt if "高度会話OS" in old_prompt else prompt + "\n\n" + old_prompt
            cur.execute(
                """
                update character_memory_summary
                   set summary_json=?, prompt_text=?, updated_at=?
                 where id=?
                """,
                (
                    json.dumps(summary, ensure_ascii=False),
                    new_prompt,
                    now,
                    summary_row["id"],
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
                    json.dumps(payload, ensure_ascii=False),
                    prompt,
                    0,
                    0,
                    now,
                    now,
                ),
            )

        existing_note = cur.execute(
            """
            select id from character_memory_note
             where character_id=? and user_id=? and source_ref=?
             order by id desc limit 1
            """,
            (character_id, USER_ID, SOURCE_REF),
        ).fetchone()
        if existing_note:
            cur.execute(
                """
                update character_memory_note
                   set category=?, note=?, confidence=?, enabled=?, pinned=?, updated_at=?
                 where id=?
                """,
                (
                    "advanced_conversation_os",
                    note,
                    1.0,
                    1,
                    1,
                    now,
                    existing_note["id"],
                ),
            )
        else:
            cur.execute(
                """
                insert into character_memory_note
                    (character_id, category, note, source_type, source_ref, confidence, enabled, pinned, created_at, updated_at, user_id)
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    character_id,
                    "advanced_conversation_os",
                    note,
                    "manual_correction",
                    SOURCE_REF,
                    1.0,
                    1,
                    1,
                    now,
                    now,
                    USER_ID,
                ),
            )

        updated.append((character_id, name, rooms_updated))

    conn.commit()

    print("OK advanced conversation OS")
    for character_id, name, rooms_updated in updated:
        pinned = cur.execute(
            """
            select count(*) from character_memory_note
             where character_id=? and user_id=? and source_ref=? and enabled=1 and pinned=1
            """,
            (character_id, USER_ID, SOURCE_REF),
        ).fetchone()[0]
        rooms = cur.execute(
            """
            select count(*) from live_chat_room
             where character_id=? and deleted_at is null and status='published'
               and conversation_objective like ?
            """,
            (character_id, f"%{MARKER}%"),
        ).fetchone()[0]
        print(
            json.dumps(
                {
                    "id": character_id,
                    "name": name,
                    "rooms_with_advanced_os": rooms,
                    "pinned_advanced_os": pinned,
                    "room_rows_touched": rooms_updated,
                },
                ensure_ascii=True,
            )
        )


if __name__ == "__main__":
    main()
