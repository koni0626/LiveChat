CREATE TABLE IF NOT EXISTS inventory_item (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  project_id INTEGER NOT NULL,
  asset_id INTEGER NOT NULL,
  target_character_id INTEGER NULL,
  name VARCHAR(255) NOT NULL,
  description TEXT NULL,
  tags_json TEXT NULL,
  source_prompt TEXT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'available',
  used_session_id INTEGER NULL,
  used_character_id INTEGER NULL,
  used_at TEXT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES user(id),
  FOREIGN KEY (project_id) REFERENCES project(id),
  FOREIGN KEY (asset_id) REFERENCES asset(id),
  FOREIGN KEY (target_character_id) REFERENCES character(id),
  FOREIGN KEY (used_session_id) REFERENCES chat_session(id),
  FOREIGN KEY (used_character_id) REFERENCES character(id)
);

CREATE INDEX IF NOT EXISTS idx_inventory_item_user_project_status
  ON inventory_item(user_id, project_id, status);

CREATE INDEX IF NOT EXISTS idx_inventory_item_target_character
  ON inventory_item(target_character_id);
