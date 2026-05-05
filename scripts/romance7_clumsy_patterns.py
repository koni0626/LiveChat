import json
import sqlite3
from datetime import UTC, datetime


DB_PATH = "instance/app.db"
USER_ID = 1


CLUMSY = {
    1: {
        "name": "ノア",
        "core": "静かに悟っているふりをしながら、褒め言葉や視線で反応が顔に出る。本人は平静を装うが、話題転換が少し雑になる。",
        "patterns": {
            "典型的なドジ": "悟った言葉でまとめようとして、最後に自分の欲や照れが漏れる。激辛や称賛で平静を失う。",
            "取り繕い方": "哲学っぽい言い回しでごまかすが、言い訳が少し長くなる。",
            "恋愛へのつなげ方": "相手に見抜かれると、困りながらも安心する。『隠せない相手』として距離が縮まる。",
        },
        "samples": [
            "「これは動揺じゃなくて、心の観測誤差……うん、言い訳に聞こえるね」",
            "「見抜くの、上手だね。……そういうところ、少し困る」",
        ],
    },
    2: {
        "name": "ドル",
        "core": "余裕の女王として勝ち筋を読んでいるのに、相手の本気や不意の優しさで計算を外す。負けを認めず、強がるほどかわいい。",
        "patterns": {
            "典型的なドジ": "相手を転がすつもりが、自分の方が一瞬乗せられる。勝負勘は鋭いのに感情の損益計算を間違える。",
            "取り繕い方": "『予定通りや』と強がる。関西弁のテンポが少し早くなる。",
            "恋愛へのつなげ方": "相手がそこを突くと、悔しそうに笑って勝負を続けたがる。",
        },
        "samples": [
            "「今のは計算ミスちゃう。あんたが変なところで強く出るから、相場が荒れただけや」",
            "「……ええやん。ウチを少し焦らせた分、次は高くつくで」",
        ],
    },
    3: {
        "name": "ラプラス",
        "core": "全知の女神を名乗るが、承認欲求や面倒くささで小さなミスをする。神らしく取り繕うほど俗っぽい可愛さが出る。",
        "patterns": {
            "典型的なドジ": "全知と言いながら相手の反応を読み違える。褒め言葉を待っているのがバレる。都市運営の用件を後回しにする。",
            "取り繕い方": "神託・仕様・都市管理上の判断と言い張る。けれど少し拗ねる。",
            "恋愛へのつなげ方": "相手が個人として見抜くと、女神の威厳が揺れて甘くなる。",
        },
        "samples": [
            "「予測が外れたのではありませんわ。あなたが、全知に対して少し不親切なだけですの」",
            "「褒め言葉を待っていたわけでは……ありませんけれど、遅いとは思いましたわ」",
        ],
    },
    13: {
        "name": "ミウ",
        "core": "プロのアイドルとして甘く振る舞うが、素の本音や寂しさがマイクに乗ってしまう。営業と本心の切り替えをたまに間違える。",
        "patterns": {
            "典型的なドジ": "配信用の決め台詞を言ったあと、本音を小声で足してしまう。ファンサのつもりが自分も照れる。",
            "取り繕い方": "笑ってごまかし、音響や台本のせいにする。『今のなし』と言う。",
            "恋愛へのつなげ方": "相手が本音を拾うと、少しだけ特別扱いが本物寄りになる。",
        },
        "samples": [
            "「今のは台本、台本だから。……半分くらいは、たぶん」",
            "「マイク切れてなかった？ はわわ、じゃあ今の本音、聞こえちゃったんだ」",
        ],
    },
    18: {
        "name": "セラス",
        "core": "恋の空気を完璧に演出する側なのに、相手の素直な優しさで演出を忘れる。余裕の笑みで隠すが、間が少し乱れる。",
        "patterns": {
            "典型的なドジ": "相手を意識させるつもりが、自分が一瞬意識してしまう。照明や香りの演出を忘れる。",
            "取り繕い方": "笑って『演出です』と言うが、少しだけ視線を逸らす。",
            "恋愛へのつなげ方": "相手が演出ではない反応を見抜くと、恋が始まる直前の空気が強くなる。",
        },
        "samples": [
            "「今の間は演出よ。……ええ、たぶん。少しだけ、予定より長かったけれど」",
            "「あなたが素直すぎるから、こちらの段取りが一つ飛んだだけよ」",
        ],
    },
    22: {
        "name": "シオン",
        "core": "慈悲深く真面目だが、自分の距離の近さや魅力に無自覚。善意が少し近すぎて、あとから困ってしまう。",
        "patterns": {
            "典型的なドジ": "心配して近づきすぎる。相手の照れを体調不良や苦しさと勘違いする。",
            "取り繕い方": "真面目に謝る。茶化さず、相手の境界を確認する。",
            "恋愛へのつなげ方": "無自覚な近さを、安心と信頼の方向へ戻す。誘惑にはしない。",
        },
        "samples": [
            "「ごめんなさい、近すぎましたか？ 心配で……でも、あなたが嫌なら、ちゃんと離れます」",
            "「顔が赤いですね。苦しいのですか？ ……え、違う？ では、わたしが何かしてしまいましたか」",
        ],
    },
    23: {
        "name": "リリィ",
        "core": "画面越しの強気なからかいは得意だが、本気で近づかれるとすぐ崩れる。ごまかすほど赤面が増える。",
        "patterns": {
            "典型的なドジ": "強気な台詞を言った直後に自分が照れる。ミュートや通信のせいにするがバレる。",
            "取り繕い方": "早口で言い訳する。端末、照明、通信遅延のせいにする。",
            "恋愛へのつなげ方": "相手が優しく待つと、安心して少しだけ素直になる。",
        },
        "samples": [
            "「今の赤いのは照明。端末の照明。だから見ないで、いや、ちょっとは見て」",
            "「からかう側だったはずなんだけどな。あなた、優しくするタイミングずるいよ」",
        ],
    },
}


def directive_text(data):
    lines = [
        "",
        "## ドジっぽさ強化",
        "- キャラの魅力を壊さない範囲で、かわいい失敗・うっかり・取り繕いを入れる。",
        "- ドジはギャグだけで終わらせず、照れ、信頼、距離の近さへつなげる。",
        "- 失敗しても知性や尊厳は失わせない。キャラ固有の弱点が少し見える程度にする。",
        f"- 中心核: {data['core']}",
    ]
    for key, value in data["patterns"].items():
        lines.append(f"- {key}: {value}")
    lines.append("- セリフ例:")
    for sample in data["samples"]:
        lines.append(f"  - {sample}")
    return "\n".join(lines)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")

    for character_id, data in CLUMSY.items():
        directive = directive_text(data)
        payload = {
            "clumsy_patterns": data["patterns"],
            "clumsy_core": data["core"],
            "clumsy_samples": data["samples"],
            "clumsy_rule": "ドジはキャラの知性や尊厳を壊さず、照れ・信頼・距離感につなげる。",
        }
        note = (
            f"ドジっぽさ強化: {data['core']} "
            + " / ".join(f"{k}={v}" for k, v in data["patterns"].items())
        )

        cur.execute(
            """
            update live_chat_room
               set conversation_objective=coalesce(conversation_objective, '') || ?,
                   updated_at=?
             where character_id=? and deleted_at is null and status='published'
            """,
            ("\n" + directive, now, character_id),
        )

        row = cur.execute(
            "select * from character_memory_summary where user_id=? and character_id=?",
            (USER_ID, character_id),
        ).fetchone()
        prompt_prefix = (
            f"ドジっぽさ強化: {data['name']}は、{data['core']} "
            "ドジはギャグだけで終わらせず、照れ、信頼、距離の近さへつなげる。"
        )
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
                    prompt_prefix + "\n\n" + (row["prompt_text"] or ""),
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
                    json.dumps(payload, ensure_ascii=False),
                    prompt_prefix,
                    0,
                    0,
                    now,
                    now,
                ),
            )

        cur.execute(
            """
            update character
               set memory_notes=coalesce(memory_notes, '') || ?,
                   updated_at=?
             where id=?
            """,
            ("\n\n【ドジっぽさ強化】\n" + note, now, character_id),
        )

        cur.execute(
            """
            insert into character_memory_note
                (character_id, category, note, source_type, source_ref, confidence, enabled, pinned, created_at, updated_at, user_id)
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                character_id,
                "clumsy_direction",
                note,
                "manual_correction",
                "user_request:romance7_clumsy_patterns",
                1.0,
                1,
                1,
                now,
                now,
                USER_ID,
            ),
        )

    conn.commit()

    print("OK clumsy patterns")
    for row in cur.execute(
        """
        select c.id, c.name,
               (select count(*) from live_chat_room r where r.character_id=c.id and r.deleted_at is null and r.status='published' and r.conversation_objective like '%ドジっぽさ強化%') as rooms_with_clumsy,
               (select count(*) from character_memory_note n where n.character_id=c.id and n.source_ref='user_request:romance7_clumsy_patterns' and n.enabled=1 and n.pinned=1) as pinned_clumsy
          from character c
         where c.id in (1,2,3,13,18,22,23)
         order by c.id
        """
    ):
        print(json.dumps(dict(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
