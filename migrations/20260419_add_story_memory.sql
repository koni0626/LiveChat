CREATE TABLE IF NOT EXISTS story_memory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL,
  chapter_id INTEGER NULL,
  scene_id INTEGER NULL,
  memory_type TEXT NOT NULL,
  memory_key TEXT NOT NULL,
  content_text TEXT NOT NULL,
  detail_json TEXT NULL,
  importance INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (project_id) REFERENCES project(id),
  FOREIGN KEY (chapter_id) REFERENCES chapter(id),
  FOREIGN KEY (scene_id) REFERENCES scene(id)
);

CREATE INDEX IF NOT EXISTS idx_story_memory_project ON story_memory(project_id);
CREATE INDEX IF NOT EXISTS idx_story_memory_chapter ON story_memory(chapter_id);
CREATE INDEX IF NOT EXISTS idx_story_memory_type_key ON story_memory(memory_type, memory_key);
