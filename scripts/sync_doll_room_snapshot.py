import json
import sqlite3
from datetime import UTC, datetime


DB_PATH = "instance/app.db"
ROOM_ID = 15


def loads_object(value):
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    room = cur.execute(
        """
        select r.id, r.title, r.conversation_objective, r.proxy_player_objective,
               r.proxy_player_gender, r.proxy_player_speech_style, r.character_id,
               c.name as character_name, r.status, r.updated_at
          from live_chat_room r
          left join character c on c.id = r.character_id
         where r.id = ? and r.deleted_at is null
        """,
        (ROOM_ID,),
    ).fetchone()
    if not room:
        raise SystemExit(f"room {ROOM_ID} not found")

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
    snapshot_patch = {
        "room_id": room["id"],
        "room_title": room["title"],
        "conversation_objective": room["conversation_objective"] or "",
        "proxy_player_objective": room["proxy_player_objective"],
        "proxy_player_gender": room["proxy_player_gender"],
        "proxy_player_speech_style": room["proxy_player_speech_style"],
        "character_id": room["character_id"],
        "character_name": room["character_name"],
        "status": room["status"],
        "version_updated_at": room["updated_at"],
    }
    settings_patch = {
        "conversation_objective": room["conversation_objective"] or "",
        "proxy_player_objective": room["proxy_player_objective"],
        "proxy_player_gender": room["proxy_player_gender"],
        "proxy_player_speech_style": room["proxy_player_speech_style"],
    }

    sessions = cur.execute(
        "select id, room_snapshot_json, settings_json from chat_session where room_id = ?",
        (ROOM_ID,),
    ).fetchall()
    for session in sessions:
        snapshot = loads_object(session["room_snapshot_json"])
        settings = loads_object(session["settings_json"])
        selected_ids = settings.get("selected_character_ids") or [room["character_id"]]
        snapshot.update(snapshot_patch)
        settings.update(settings_patch)
        settings["selected_character_ids"] = selected_ids
        cur.execute(
            """
            update chat_session
               set room_snapshot_json = ?,
                   settings_json = ?,
                   updated_at = ?
             where id = ?
            """,
            (
                json.dumps(snapshot, ensure_ascii=False),
                json.dumps(settings, ensure_ascii=False),
                now,
                session["id"],
            ),
        )

    conn.commit()
    print(f"synced {len(sessions)} sessions for room {ROOM_ID}")
    for row in cur.execute(
        """
        select id, title,
               json_extract(room_snapshot_json, '$.conversation_objective') as snapshot_objective,
               json_extract(settings_json, '$.conversation_objective') as settings_objective
          from chat_session
         where room_id = ?
         order by id desc
        """,
        (ROOM_ID,),
    ):
        print(
            json.dumps(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "snapshot_objective": row["snapshot_objective"],
                    "settings_objective": row["settings_objective"],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
