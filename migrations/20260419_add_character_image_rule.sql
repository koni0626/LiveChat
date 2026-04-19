CREATE TABLE IF NOT EXISTS character_image_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER NOT NULL UNIQUE,
    hair_rule TEXT,
    face_rule TEXT,
    ear_rule TEXT,
    accessory_rule TEXT,
    outfit_rule TEXT,
    style_rule TEXT,
    negative_rule TEXT,
    default_quality TEXT NOT NULL DEFAULT 'low',
    default_size TEXT NOT NULL DEFAULT '1024x1024',
    prompt_prefix TEXT,
    prompt_suffix TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES character(id)
);

CREATE INDEX IF NOT EXISTS ix_character_image_rule_character_id
    ON character_image_rule (character_id);
