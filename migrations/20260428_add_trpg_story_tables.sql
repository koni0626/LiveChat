CREATE TABLE IF NOT EXISTS story (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  character_id INTEGER NOT NULL,
  created_by_user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  description TEXT NULL,
  status TEXT NOT NULL DEFAULT 'draft',
  story_mode TEXT NOT NULL DEFAULT 'free_chat',
  config_markdown TEXT NULL,
  config_json TEXT NULL,
  initial_state_json TEXT NULL,
  style_reference_asset_id INTEGER NULL,
  main_character_reference_asset_id INTEGER NULL,
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT NULL,
  FOREIGN KEY (project_id) REFERENCES project(id),
  FOREIGN KEY (character_id) REFERENCES character(id),
  FOREIGN KEY (created_by_user_id) REFERENCES user(id),
  FOREIGN KEY (style_reference_asset_id) REFERENCES asset(id),
  FOREIGN KEY (main_character_reference_asset_id) REFERENCES asset(id)
);

CREATE INDEX IF NOT EXISTS idx_story_project_id ON story(project_id);
CREATE INDEX IF NOT EXISTS idx_story_character_id ON story(character_id);
CREATE INDEX IF NOT EXISTS idx_story_status ON story(status);
CREATE INDEX IF NOT EXISTS idx_story_story_mode ON story(story_mode);

CREATE TABLE IF NOT EXISTS story_session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  story_id INTEGER NOT NULL,
  owner_user_id INTEGER NOT NULL,
  title TEXT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  privacy_status TEXT NOT NULL DEFAULT 'private',
  player_name TEXT NULL,
  active_image_id INTEGER NULL,
  story_snapshot_json TEXT NULL,
  settings_json TEXT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT NULL,
  FOREIGN KEY (project_id) REFERENCES project(id),
  FOREIGN KEY (story_id) REFERENCES story(id),
  FOREIGN KEY (owner_user_id) REFERENCES user(id),
  FOREIGN KEY (active_image_id) REFERENCES asset(id)
);

CREATE INDEX IF NOT EXISTS idx_story_session_project_id ON story_session(project_id);
CREATE INDEX IF NOT EXISTS idx_story_session_story_id ON story_session(story_id);
CREATE INDEX IF NOT EXISTS idx_story_session_owner_user_id ON story_session(owner_user_id);

CREATE TABLE IF NOT EXISTS story_session_state (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL UNIQUE,
  state_json TEXT NOT NULL DEFAULT '{}',
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES story_session(id)
);

CREATE TABLE IF NOT EXISTS story_message (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  sender_type TEXT NOT NULL,
  speaker_name TEXT NULL,
  message_text TEXT NOT NULL,
  message_type TEXT NOT NULL DEFAULT 'dialogue',
  order_no INTEGER NOT NULL,
  metadata_json TEXT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TEXT NULL,
  FOREIGN KEY (session_id) REFERENCES story_session(id)
);

CREATE INDEX IF NOT EXISTS idx_story_message_session_id ON story_message(session_id);
CREATE INDEX IF NOT EXISTS idx_story_message_order_no ON story_message(session_id, order_no);

CREATE TABLE IF NOT EXISTS story_roll_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  message_id INTEGER NULL,
  formula TEXT NOT NULL,
  dice_json TEXT NOT NULL,
  modifier INTEGER NOT NULL DEFAULT 0,
  total INTEGER NOT NULL,
  target INTEGER NULL,
  outcome TEXT NULL,
  reason TEXT NULL,
  metadata_json TEXT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES story_session(id),
  FOREIGN KEY (message_id) REFERENCES story_message(id)
);

CREATE INDEX IF NOT EXISTS idx_story_roll_log_session_id ON story_roll_log(session_id);

CREATE TABLE IF NOT EXISTS story_image (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  asset_id INTEGER NOT NULL,
  source_message_id INTEGER NULL,
  visual_type TEXT NOT NULL DEFAULT 'scene',
  subject TEXT NULL,
  prompt_text TEXT NULL,
  reference_asset_ids_json TEXT NULL,
  metadata_json TEXT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (session_id) REFERENCES story_session(id),
  FOREIGN KEY (asset_id) REFERENCES asset(id),
  FOREIGN KEY (source_message_id) REFERENCES story_message(id)
);

CREATE INDEX IF NOT EXISTS idx_story_image_session_id ON story_image(session_id);
CREATE INDEX IF NOT EXISTS idx_story_image_asset_id ON story_image(asset_id);
