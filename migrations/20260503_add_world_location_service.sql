CREATE TABLE IF NOT EXISTS world_location_service (
  id INTEGER PRIMARY KEY,
  location_id INTEGER NOT NULL,
  project_id INTEGER NOT NULL,
  name VARCHAR(255) NOT NULL,
  service_type VARCHAR(100),
  summary TEXT,
  chat_hook TEXT,
  visual_prompt TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'published',
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at DATETIME,
  FOREIGN KEY(location_id) REFERENCES world_location(id),
  FOREIGN KEY(project_id) REFERENCES project(id)
);

CREATE INDEX IF NOT EXISTS ix_world_location_service_location_id ON world_location_service(location_id);
CREATE INDEX IF NOT EXISTS ix_world_location_service_project_id ON world_location_service(project_id);
