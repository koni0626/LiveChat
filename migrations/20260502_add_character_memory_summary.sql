CREATE TABLE IF NOT EXISTS character_memory_summary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NULL,
  character_id INTEGER NOT NULL,
  summary_json TEXT NULL,
  prompt_text TEXT NULL,
  source_note_count INTEGER NOT NULL DEFAULT 0,
  source_note_max_id INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES user(id),
  FOREIGN KEY (character_id) REFERENCES character(id),
  UNIQUE (user_id, character_id)
);

CREATE INDEX IF NOT EXISTS idx_character_memory_summary_user_character
  ON character_memory_summary(user_id, character_id);

CREATE INDEX IF NOT EXISTS idx_character_memory_summary_character_id
  ON character_memory_summary(character_id);
