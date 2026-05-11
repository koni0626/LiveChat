from __future__ import annotations


ROMANCE_GENRE = "romance"
LEARNING_GENRE = "learning"
VALID_LIVE_CHAT_GENRES = {ROMANCE_GENRE, LEARNING_GENRE}


def normalize_live_chat_genre(value) -> str:
    genre = str(value or ROMANCE_GENRE).strip().lower()
    return genre if genre in VALID_LIVE_CHAT_GENRES else ROMANCE_GENRE


def genre_from_session(session, *, room=None, serializer=None) -> str:
    if room is not None:
        return normalize_live_chat_genre(getattr(room, "genre", None))
    if serializer is not None and session is not None:
        room_snapshot = serializer.load_json(getattr(session, "room_snapshot_json", None)) or {}
        if isinstance(room_snapshot, dict) and room_snapshot.get("genre"):
            return normalize_live_chat_genre(room_snapshot.get("genre"))
        settings = serializer.load_json(getattr(session, "settings_json", None)) or {}
        if isinstance(settings, dict):
            return normalize_live_chat_genre(settings.get("live_chat_genre") or settings.get("genre"))
    return ROMANCE_GENRE


def genre_from_context(context: dict | None) -> str:
    context = context or {}
    room = context.get("room") or {}
    if isinstance(room, dict) and room.get("genre"):
        return normalize_live_chat_genre(room.get("genre"))
    session = context.get("session") or {}
    if isinstance(session, dict):
        snapshot = session.get("room_snapshot_json") or {}
        if isinstance(snapshot, dict) and snapshot.get("genre"):
            return normalize_live_chat_genre(snapshot.get("genre"))
        settings = session.get("settings_json") or {}
        if isinstance(settings, dict):
            return normalize_live_chat_genre(settings.get("live_chat_genre") or settings.get("genre"))
    return ROMANCE_GENRE
