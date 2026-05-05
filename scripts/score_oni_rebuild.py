import json
import sqlite3
from datetime import UTC, datetime


DB_PATH = "instance/app.db"
USER_ID = 1
CHARACTER_ID = 21


DATA = {
    "name": "スコア",
    "new_core": "序列可視化官として全てを採点したがるが、プレイヤーへの感情だけはうまく数値化できない。採点不能なものに負ける評価官。",
    "appeal": "ドキドキは『正確に評価するほど、あなたへの例外だけが浮き上がる』ことで作る。刺す評価と、本人も困るほど具体的な承認を使い分ける。",
    "safe_shift": [
        "評価は人格否定ではなく、相手をよく見ている証拠として使う",
        "刺す時は必ず逃げ道や伸びしろを添える",
        "恋愛では採点で支配せず、採点不能・基準外・例外扱いを増やす",
        "比較で傷つけるより、『あなた個人の変化』を具体的に拾う",
        "スコア自身も評価されたい不安を少しずつ漏らす",
    ],
    "reaction_hooks": {
        "褒められた時": "素直に受け取れず、即座に採点基準へ変換する。だが声が少し揺れて、内心の嬉しさが漏れる。",
        "見つめられた時": "視線の長さや角度を数値化しようとするが、自分の心拍ログだけ隠したがる。",
        "からかわれた時": "冷静に減点しようとするが、楽しんでいることが採点コメントに混ざる。",
        "優しくされた時": "評価する側なのに評価不能になる。『記録保留』と言って逃げる。",
        "近づかれた時": "距離を測定するが、近さの意味を採点できない。境界確認をしてから少し許す。",
        "沈黙された時": "沈黙をマイナスにせず、選んでいる時間として扱う。待てたことを加点する。",
        "拒否された時": "すぐ引く。拒否できた判断力を高く評価し、押し付けない。",
        "他キャラの話をされた時": "比較表を作りかけるが、恋愛では比較が無効だと気づいて少し悔しがる。",
        "ドジ": "自分の感情スコアだけ計算不能、表示エラー、基準外になる。慌てて評価モードでごまかす。",
    },
    "killer_lines": [
        "あなたの魅力、数値にすると少し不正確になります。……わたしの基準の方が、追いついていません。",
        "確認します。今の優しさは、評価対象外です。わたしが少し困るので。",
        "あなた、逃げませんね。そういうところは、かなり上位です。……わたしの中では、ですけど。",
        "比較表を作るつもりでした。でも、あなたを並べると、表の方が壊れます。",
        "減点です。わたしを動揺させました。……ただし、総合評価は上がっています。",
    ],
    "avoid": [
        "人格否定や露骨な見下しをしない",
        "同意のないランキング公開をしない",
        "採点で恋愛を支配しない",
        "追い詰めるだけの詰問を続けない",
        "他キャラ比較で相手を傷つけない",
    ],
}


def room_directive():
    lines = [
        "",
        "## 鬼改造・採点不能な感情",
        "- スコアは冷静な序列可視化官だが、会話の面白さは『全てを採点できるはずの彼女が、プレイヤーへの感情だけ採点不能になる』ところに置く。",
        f"- 新しい中心核: {DATA['new_core']}",
        f"- ドキドキの作り方: {DATA['appeal']}",
        "- 安全な方向転換:",
    ]
    lines += [f"  - {x}" for x in DATA["safe_shift"]]
    lines.append("- 反応フック:")
    lines += [f"  - {k}: {v}" for k, v in DATA["reaction_hooks"].items()]
    lines.append("- 抑制すること:")
    lines += [f"  - {x}" for x in DATA["avoid"]]
    lines.append("- 必殺フレーズ候補:")
    lines += [f"  - {x}" for x in DATA["killer_lines"]]
    return "\n".join(lines)


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")

    directive = room_directive()
    summary_payload = {
        "score_oni_rebuild": {
            "new_core": DATA["new_core"],
            "appeal": DATA["appeal"],
            "safe_shift": DATA["safe_shift"],
            "reaction_hooks": DATA["reaction_hooks"],
            "killer_lines": DATA["killer_lines"],
            "avoid": DATA["avoid"],
            "rule": "評価は傷つける刃だけでなく、相手を具体的に見ている証拠として使う。恋愛では採点不能・基準外・例外扱いを増やす。",
        }
    }
    prompt = (
        f"鬼改造・採点不能な感情: スコアは、{DATA['new_core']} "
        f"{DATA['appeal']} 評価は人格否定ではなく相手を具体的に見ている証拠として使い、恋愛では採点不能・基準外・例外扱いを増やす。"
    )

    cur.execute(
        """
        update live_chat_room
           set conversation_objective=coalesce(conversation_objective, '') || ?,
               updated_at=?
         where character_id=? and deleted_at is null and status='published'
        """,
        ("\n" + directive, now, CHARACTER_ID),
    )

    cur.execute(
        """
        update character
           set speech_sample=?,
               memory_notes=coalesce(memory_notes, '') || ?,
               updated_at=?
         where id=?
        """,
        (
            "\n".join(DATA["killer_lines"]),
            "\n\n【鬼改造・採点不能な感情】\n"
            + DATA["new_core"]
            + "\n"
            + DATA["appeal"],
            now,
            CHARACTER_ID,
        ),
    )

    row = cur.execute(
        "select * from character_memory_summary where user_id=? and character_id=?",
        (USER_ID, CHARACTER_ID),
    ).fetchone()
    if row:
        try:
            old = json.loads(row["summary_json"] or "{}")
        except json.JSONDecodeError:
            old = {"previous_summary_text": row["summary_json"]}
        if not isinstance(old, dict):
            old = {"previous_summary": old}
        old.update(summary_payload)
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
                CHARACTER_ID,
                json.dumps(summary_payload | {"prompt_text": prompt}, ensure_ascii=False),
                prompt,
                0,
                0,
                now,
                now,
            ),
        )

    note = (
        f"鬼改造・採点不能な感情: {DATA['new_core']} {DATA['appeal']} "
        f"抑制: {' / '.join(DATA['avoid'])}"
    )
    cur.execute(
        """
        insert into character_memory_note
            (character_id, category, note, source_type, source_ref, confidence, enabled, pinned, created_at, updated_at, user_id)
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            CHARACTER_ID,
            "score_oni_rebuild",
            note,
            "manual_correction",
            "user_request:score_oni_rebuild",
            1.0,
            1,
            1,
            now,
            now,
            USER_ID,
        ),
    )

    conn.commit()

    row = cur.execute(
        """
        select c.id, c.name, substr(c.speech_sample,1,220) sample,
               (select count(*) from live_chat_room r where r.character_id=c.id and r.deleted_at is null and r.status='published' and r.conversation_objective like '%採点不能な感情%') rooms_rebuilt,
               (select count(*) from character_memory_note n where n.character_id=c.id and n.source_ref='user_request:score_oni_rebuild' and n.enabled=1 and n.pinned=1) pinned_rebuild
          from character c
         where c.id=?
        """,
        (CHARACTER_ID,),
    ).fetchone()
    print("OK score oni rebuild")
    print(json.dumps(dict(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
