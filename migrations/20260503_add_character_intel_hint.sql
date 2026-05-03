CREATE TABLE IF NOT EXISTS character_intel_hint (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL,
  project_id INTEGER NOT NULL,
  target_character_id INTEGER NOT NULL,
  source_character_id INTEGER NOT NULL,
  topic VARCHAR(255) NOT NULL,
  hint_text TEXT NOT NULL,
  reveal_threshold INTEGER NOT NULL DEFAULT 40,
  status VARCHAR(50) NOT NULL DEFAULT 'revealed',
  revealed_at DATETIME,
  used_at DATETIME,
  created_at DATETIME,
  updated_at DATETIME,
  FOREIGN KEY(user_id) REFERENCES user(id),
  FOREIGN KEY(project_id) REFERENCES project(id),
  FOREIGN KEY(target_character_id) REFERENCES character(id),
  FOREIGN KEY(source_character_id) REFERENCES character(id),
  CONSTRAINT uq_character_intel_hint_user_target_source_topic UNIQUE (user_id, target_character_id, source_character_id, topic)
);
CREATE INDEX IF NOT EXISTS ix_character_intel_hint_user_id ON character_intel_hint(user_id);
CREATE INDEX IF NOT EXISTS ix_character_intel_hint_project_id ON character_intel_hint(project_id);
CREATE INDEX IF NOT EXISTS ix_character_intel_hint_target_character_id ON character_intel_hint(target_character_id);
CREATE INDEX IF NOT EXISTS ix_character_intel_hint_source_character_id ON character_intel_hint(source_character_id);
