CREATE TABLE IF NOT EXISTS character_outfit (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    asset_id INTEGER NOT NULL,
    thumbnail_asset_id INTEGER,
    tags_json TEXT,
    usage_scene VARCHAR(80),
    season VARCHAR(80),
    mood VARCHAR(80),
    color_notes TEXT,
    fixed_parts TEXT,
    allowed_changes TEXT,
    ng_rules TEXT,
    prompt_notes TEXT,
    is_default BOOLEAN NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME,
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(character_id) REFERENCES character (id),
    FOREIGN KEY(asset_id) REFERENCES asset (id),
    FOREIGN KEY(thumbnail_asset_id) REFERENCES asset (id)
);

CREATE INDEX IF NOT EXISTS ix_character_outfit_project_id ON character_outfit (project_id);
CREATE INDEX IF NOT EXISTS ix_character_outfit_character_id ON character_outfit (character_id);
CREATE INDEX IF NOT EXISTS ix_character_outfit_asset_id ON character_outfit (asset_id);
CREATE INDEX IF NOT EXISTS ix_character_outfit_thumbnail_asset_id ON character_outfit (thumbnail_asset_id);
CREATE INDEX IF NOT EXISTS ix_character_outfit_usage_scene ON character_outfit (usage_scene);
CREATE INDEX IF NOT EXISTS ix_character_outfit_season ON character_outfit (season);
CREATE INDEX IF NOT EXISTS ix_character_outfit_mood ON character_outfit (mood);
CREATE INDEX IF NOT EXISTS ix_character_outfit_is_default ON character_outfit (is_default);
CREATE INDEX IF NOT EXISTS ix_character_outfit_status ON character_outfit (status);
