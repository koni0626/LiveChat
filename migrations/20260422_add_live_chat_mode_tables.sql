CREATE TABLE IF NOT EXISTS chat_session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  title TEXT,
  session_type TEXT NOT NULL DEFAULT 'live_chat',
  status TEXT NOT NULL DEFAULT 'active',
  active_image_id INTEGER NULL,
  player_name TEXT NULL,
  settings_json TEXT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT NULL,
  FOREIGN KEY (project_id) REFERENCES project(id),
  FOREIGN KEY (active_image_id) REFERENCES asset(id)
);

CREATE INDEX IF NOT EXISTS idx_chat_session_project_id ON chat_session(project_id);

CREATE TABLE IF NOT EXISTS chat_message (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  sender_type TEXT NOT NULL,
  speaker_name TEXT NULL,
  message_text TEXT NOT NULL,
  order_no INTEGER NOT NULL,
  message_role TEXT NULL,
  state_snapshot_json TEXT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES chat_session(id)
);

CREATE INDEX IF NOT EXISTS idx_chat_message_session_id ON chat_message(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_message_order_no ON chat_message(session_id, order_no);

CREATE TABLE IF NOT EXISTS session_state (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL UNIQUE,
  state_json TEXT NOT NULL DEFAULT '{}',
  narration_note TEXT NULL,
  visual_prompt_text TEXT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES chat_session(id)
);

CREATE TABLE IF NOT EXISTS session_character (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  character_id INTEGER NOT NULL,
  role_type TEXT NOT NULL DEFAULT 'main',
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES chat_session(id),
  FOREIGN KEY (character_id) REFERENCES character(id)
);

CREATE INDEX IF NOT EXISTS idx_session_character_session_id ON session_character(session_id);
CREATE INDEX IF NOT EXISTS idx_session_character_character_id ON session_character(character_id);

CREATE TABLE IF NOT EXISTS session_image (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  asset_id INTEGER NOT NULL,
  image_type TEXT NOT NULL,
  prompt_text TEXT NULL,
  state_json TEXT NULL,
  quality TEXT NULL,
  size TEXT NULL,
  is_selected INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES chat_session(id),
  FOREIGN KEY (asset_id) REFERENCES asset(id)
);

CREATE INDEX IF NOT EXISTS idx_session_image_session_id ON session_image(session_id);
