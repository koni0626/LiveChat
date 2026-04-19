CREATE TABLE IF NOT EXISTS scene_character (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scene_id) REFERENCES scene (id),
    FOREIGN KEY (character_id) REFERENCES character (id)
);

CREATE INDEX IF NOT EXISTS idx_scene_character_scene_id
    ON scene_character (scene_id);

CREATE INDEX IF NOT EXISTS idx_scene_character_character_id
    ON scene_character (character_id);
