CREATE TABLE IF NOT EXISTS user_setting (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL UNIQUE,
  text_ai_model VARCHAR(100) NOT NULL DEFAULT 'gpt-5.4-mini',
  image_ai_model VARCHAR(100) NOT NULL DEFAULT 'gpt-image-1.5',
  default_quality VARCHAR(20) NOT NULL DEFAULT 'medium',
  default_size VARCHAR(20) NOT NULL DEFAULT '1024x1024',
  autosave_interval VARCHAR(20) NOT NULL DEFAULT 'off',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(user_id) REFERENCES user(id)
);

CREATE INDEX IF NOT EXISTS ix_user_setting_user_id ON user_setting(user_id);
