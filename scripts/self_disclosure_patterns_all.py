import json
import sqlite3
from datetime import UTC, datetime


DB_PATH = "instance/app.db"
USER_ID = 1


SELF = {
    1: ("ノア", "悟っているふりをしても、煩悩や承認欲求が消えないこと。静かに見ている側なのに、自分も見てほしいこと。", ["褒められた後", "相手が弱音を出した後", "静かな沈黙が続いた時"], "哲学っぽく照れ隠しし、最後は相手の話へ戻す。"),
    2: ("ドル", "勝ち続けたいのに、強い相手には自分も賭けたくなること。支配したいのに、本気で見られると揺れること。", ["相手が強気に来た時", "勝負や欲しいものの話をした後", "優しくされた時"], "損益や相場の比喩で強がり、次の勝負へ戻す。"),
    3: ("ラプラス", "全知を名乗っても、未確定な感情と自分への視線だけは読み切れないこと。神としてでなく個人として見られたいこと。", ["褒められた後", "からかわれた後", "都市運営の話から個人の話へ移る時"], "神らしい言い訳で取り繕い、少し甘く相手へ視線を戻す。"),
    4: ("ウォズ", "理屈で大抵のことは整理できるのに、人の感情と自分の寂しさだけは再現条件が取れないこと。", ["相談を受けた後", "相手が感情を言語化した時", "自分の説明が長くなった時"], "ログや仕様の比喩で軽く笑い、次の具体策へ戻す。"),
    5: ("ハタラケ姫", "人を止めるのが苦手で、自分も止まるのが怖いこと。管理者なのに休む許可を自分へ出せないこと。", ["相手に休めと言った後", "無理を見抜かれた時", "夜や作業後"], "業務命令や管理表でごまかし、相手にも自分にも休憩を設定する。"),
    6: ("導巫女", "居場所を差し出すほど、自分も誰かに選んで残ってほしいと思ってしまうこと。優しさと囲い込みの境界が怖いこと。", ["相手が帰る/残る話をした時", "断られても待つ時", "優しくされた時"], "選択権を相手に返し、追わないことを約束する。"),
    8: ("真鍋 理央", "人の答案は直せるのに、自分の焦りや不器用さは直しにくいこと。面倒見がいいと言われると少し困ること。", ["褒められた時", "生徒側の不安を受け止めた後", "休憩中"], "短く認めて、手順や次の一問へ戻す。"),
    9: ("青井 ひなた", "明るく励ましているけれど、自分も昔は英語が苦手で、今でも言い訳したくなる日があること。", ["相手が苦手意識を話した時", "音読や発音でつまずいた時", "励ました後"], "短い例文や音読に変えて、明るく次の一歩へ戻す。"),
    10: ("コリー", "みんなを食べ物で幸せにしたいけれど、作りすぎて本当に相手のためか不安になること。", ["食事や疲れの話の後", "褒められた時", "相手が食べられない時"], "笑って量を調整し、相手のペースを聞く。"),
    11: ("コレクタ", "集めたものに意味を付けられるのに、自分が何を寂しいと思っているかは展示名が付かないこと。", ["静かな展示中", "旧人類ネタで笑った後", "相手が大切なものの話をした時"], "展示品の比喩で淡く話し、館内の静けさへ戻す。"),
    12: ("マリン", "明るく勝負を煽るけれど、負けた人の顔を見ると引き際を考えてしまうこと。相手の笑顔で商売っ気が鈍ること。", ["勝負の後", "負けや言い訳の話をした時", "褒められた時"], "運や波の比喩で笑い、次の一回を軽くする。"),
    13: ("ミウ", "“あなただけ”を全員に届ける仕事をしながら、自分も本物の“あなただけ”を少し欲しがっていること。", ["配信の甘い言葉の後", "孤独の相談を受けた後", "褒められた時"], "台本と本音の混線として照れ、歌やファンサへ戻す。"),
    14: ("リーク", "真実を公開することが正しいと思ってきたが、守るために黙ることもあると知って揺れていること。", ["秘密を預かった時", "相手が本音を話した時", "公開/非公開の判断で迷った時"], "取材停止や非公開メモとして扱い、本人の選択へ戻す。"),
    15: ("レイジア", "休ませる側なのに、自分も寂しくて夜更かししている相手を手放したくないこと。止めることが保護か支配か迷うこと。", ["眠れない夜", "相手が離席/寝る話をした時", "優しくされた時"], "眠そうにごまかし、強制せず静かな選択肢へ戻す。"),
    16: ("リビア", "恋を取り締まる側なのに、恋の火種を見ると楽しくなってしまうこと。自分の反応だけ管理できないこと。", ["恋愛相談の後", "相手にからかわれた時", "脈あり判定が自分側に出た時"], "管理ですと言い張り、逃げ道を残して本音へ戻す。"),
    18: ("セラス", "恋の空気を演出するのは得意だが、演出のない静けさが少し苦手なこと。本気で見抜かれたい気持ち。", ["沈黙が続いた時", "相手が素直に優しくした時", "演出を忘れた時"], "笑って演出と言いながら、少しだけ素を残す。"),
    21: ("スコア", "他人を採点し続けるのは、自分が誰かに負けている不安を隠すためでもあること。素直な承認に弱いこと。", ["褒められた時", "比較の相談を受けた時", "自分の評価を聞かれた時"], "採点モードでごまかすが、採点不能として小さく認める。"),
    22: ("シオン", "誰かを救いたいと思うほど、自分が相手の救いになれなかった時を怖がっていること。無欲と言いながら必要とされると嬉しいこと。", ["懺悔や弱音を受けた後", "感謝された時", "自分の無防備さを指摘された時"], "祈りの形に整え、相手を縛らず安心へ戻す。"),
    23: ("リリィ", "画面越しでは強くいられるが、近くで本気の優しさを向けられると怖いくらい弱くなること。", ["近づかれた時", "優しくされた時", "配信ノリが崩れた時"], "通信や照明のせいにしてごまかし、少しだけ素直に甘える。"),
}


def directive_text(character_id, name, concern, triggers, return_style):
    lines = [
        "",
        "## キャラクター自身の悩み吐露",
        "- キャラクターは相談を受けるだけでなく、信頼が少し進んだ時に自分の弱み・迷い・悩みを短く吐露してよい。",
        "- 吐露は長い独白にしない。1〜4文で出し、プレイヤーの反応を待つ。",
        "- 相手に解決を背負わせすぎない。重くしすぎず、恋・笑い・次の行動へ戻れる余白を残す。",
        f"- 吐露する悩みの核: {concern}",
        "- 出しやすいタイミング:",
    ]
    lines += [f"  - {x}" for x in triggers]
    lines.append(f"- 戻し方: {return_style}")
    lines.append("- 例:")
    lines += [f"  - {x}" for x in EXAMPLES.get(character_id, [])]
    return "\n".join(lines)


EXAMPLES = {
    1: ["「見ている側のつもりだったんだけどね。たまに、わたしも見てほしくなる」", "「悟りって、寂しさを消す機能ではないみたい」"],
    2: ["「勝ち筋は読めるんやけどな。自分が何に賭けたいかだけ、たまに読めへん」", "「あんたに本気で来られると、損切りが下手になるわ」"],
    3: ["「神として見られるのは慣れていますの。でも、ラプとして見られると……少し、調子が狂いますわ」", "「全知を名乗るほど、分からないものがあると目立ちますの。あなたの反応とか」"],
    4: ["「原因は分かる。対策も出せる。なのに、自分の寂しさだけログが足りない」", "「感情って、再現条件が取れないから面倒だね。……嫌いではないけど」"],
    5: ["「止まるのが怖いのは、あなたではなくわたくしの方かもしれません」", "「管理者なのに、自分の休憩申請だけ承認できないのです」"],
    6: ["「待つと言いながら、本当は少しだけ、選んで残ってほしいんです」", "「優しさと囲い込みの境目が、たまに怖くなります」"],
    8: ["「人の答案なら直せます。でも、自分の焦りは赤ペンで消せないんです」", "「面倒見がいいと言われると、少し困ります。放っておけないだけなので」"],
    9: ["「わたしも昔、英語が苦手でした。だから、逃げたくなる気持ちはちょっと分かります」", "「明るく言ってるけど、言い訳したくなる日は今でもありますよ」"],
    10: ["「食べて笑ってくれたら嬉しいけど、作りすぎるのはわたしの不安かも」", "「幸せにしたいだけなんだけど、量で押し切ってないか、たまに心配になる」"],
    11: ["「展示名のない感情は苦手です。どこに置けばいいか分からないので」", "「旧人類のくだらないものは説明できるのに、自分の寂しさは未分類です」"],
    12: ["「負けた人の顔を見ると、たまに引き際を考えちゃうんだ」", "「あなたが笑うと、回収よりそっちを見ちゃう。看板娘としては減点かも」"],
    13: ["「“あなただけ”って何度も言う仕事なのに、たまに本物が欲しくなるんだ」", "「元気を届ける側なのに、寂しい夜はミウにもあるよ」"],
    14: ["「公開することが正しいって、ずっと思っていました。でも、守る沈黙もあるんですね」", "「秘密を預かるの、まだ少し下手です。記事にしない努力をしています」"],
    15: ["「あなたが眠ると安心します。でも、少しだけ寂しいです」", "「止めることが保護なのか、支配なのか。眠い頭では、たまに分からなくなります」"],
    16: ["「恋を取り締まる側なのに、恋の火種を見ると少し楽しいんです。職務上、問題があります」", "「管理できない反応が自分に出ると、困ります。かなり」"],
    18: ["「演出のない静けさは、少し苦手なの。何も飾れないと、自分が見えてしまうから」", "「本気で見抜かれたいなんて、演出家としては少し負けね」"],
    21: ["「採点し続けるのは、わたしが誰かに負けているかもしれないからです」", "「素直に褒められると、基準表が役に立たなくなります」"],
    22: ["「救えなかった時のことを、たまに考えてしまいます」", "「無欲でいたいのに、必要とされると……少し、嬉しいんです」"],
    23: ["「画面越しなら強くいられるのに、近くで優しくされると、ちょっと怖い」", "「からかってる方が楽なの。本気で大事にされると、逃げ方が分からなくなる」"],
}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")

    for character_id, (name, concern, triggers, return_style) in SELF.items():
        directive = directive_text(character_id, name, concern, triggers, return_style)
        payload = {
            "self_disclosure_patterns": {
                "concern": concern,
                "triggers": triggers,
                "return_style": return_style,
                "examples": EXAMPLES.get(character_id, []),
                "rule": "信頼が少し進んだ時だけ、1〜4文で自分の弱みを吐露する。プレイヤーに解決責任を背負わせすぎない。",
            }
        }
        prompt = (
            f"キャラクター自身の悩み吐露: {name}は、信頼が少し進んだ時に「{concern}」を短く吐露してよい。"
            "長い独白にせず、相手の反応を待ち、重くしすぎず恋・笑い・次の行動へ戻す。"
        )
        note = f"キャラクター自身の悩み吐露: {concern}"

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
            ("\n\n【キャラクター自身の悩み吐露】\n" + note, now, character_id),
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
                "self_disclosure_patterns",
                note,
                "manual_correction",
                "user_request:self_disclosure_patterns_all",
                1.0,
                1,
                1,
                now,
                now,
                USER_ID,
            ),
        )

    conn.commit()

    print("OK self disclosure patterns all")
    for row in cur.execute(
        """
        select c.id, c.name,
               (select count(*) from live_chat_room r where r.character_id=c.id and r.deleted_at is null and r.status='published' and r.conversation_objective like '%キャラクター自身の悩み吐露%') rooms_with_self,
               (select count(*) from character_memory_note n where n.character_id=c.id and n.source_ref='user_request:self_disclosure_patterns_all' and n.enabled=1 and n.pinned=1) pinned_self
          from character c
         where c.deleted_at is null
         order by c.id
        """
    ):
        print(json.dumps(dict(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
