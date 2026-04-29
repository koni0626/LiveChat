CREATE TABLE IF NOT EXISTS world_location (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL,
  name VARCHAR(255) NOT NULL,
  location_type VARCHAR(100),
  description TEXT,
  owner_character_id INTEGER,
  image_asset_id INTEGER,
  source_type VARCHAR(50) NOT NULL DEFAULT 'manual',
  source_note TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'published',
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at DATETIME,
  FOREIGN KEY(project_id) REFERENCES project(id),
  FOREIGN KEY(owner_character_id) REFERENCES character(id),
  FOREIGN KEY(image_asset_id) REFERENCES asset(id)
);

CREATE INDEX IF NOT EXISTS ix_world_location_project_id ON world_location(project_id);
CREATE INDEX IF NOT EXISTS ix_world_location_owner_character_id ON world_location(owner_character_id);

CREATE TABLE IF NOT EXISTS world_map_image (
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL,
  asset_id INTEGER NOT NULL,
  title VARCHAR(255),
  description TEXT,
  prompt_text TEXT,
  source_type VARCHAR(50) NOT NULL DEFAULT 'upload',
  quality VARCHAR(50),
  size VARCHAR(50),
  is_active INTEGER NOT NULL DEFAULT 0,
  created_by_user_id INTEGER,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at DATETIME,
  FOREIGN KEY(project_id) REFERENCES project(id),
  FOREIGN KEY(asset_id) REFERENCES asset(id),
  FOREIGN KEY(created_by_user_id) REFERENCES user(id)
);

CREATE INDEX IF NOT EXISTS ix_world_map_image_project_id ON world_map_image(project_id);
