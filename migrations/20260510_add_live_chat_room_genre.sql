ALTER TABLE live_chat_room ADD COLUMN genre VARCHAR(50) NOT NULL DEFAULT 'romance';

CREATE INDEX IF NOT EXISTS ix_live_chat_room_genre ON live_chat_room (genre);
