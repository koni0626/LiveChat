ALTER TABLE live_chat_room ADD COLUMN default_outfit_id INTEGER REFERENCES character_outfit(id);
CREATE INDEX IF NOT EXISTS ix_live_chat_room_default_outfit_id ON live_chat_room(default_outfit_id);
