CREATE TABLE IF NOT EXISTS world_news_item (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    created_by_user_id INTEGER,
    related_character_id INTEGER,
    related_location_id INTEGER,
    news_type VARCHAR(80) NOT NULL DEFAULT 'location_news',
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    summary TEXT,
    importance INTEGER NOT NULL DEFAULT 3,
    source_type VARCHAR(80) NOT NULL DEFAULT 'manual_ai',
    source_ref_type VARCHAR(80),
    source_ref_id INTEGER,
    return_url VARCHAR(512),
    status VARCHAR(50) NOT NULL DEFAULT 'published',
    metadata_json TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME,
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(created_by_user_id) REFERENCES user (id),
    FOREIGN KEY(related_character_id) REFERENCES character (id),
    FOREIGN KEY(related_location_id) REFERENCES world_location (id)
);

CREATE INDEX IF NOT EXISTS ix_world_news_item_project_id ON world_news_item (project_id);
CREATE INDEX IF NOT EXISTS ix_world_news_item_created_by_user_id ON world_news_item (created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_world_news_item_related_character_id ON world_news_item (related_character_id);
CREATE INDEX IF NOT EXISTS ix_world_news_item_related_location_id ON world_news_item (related_location_id);
CREATE INDEX IF NOT EXISTS ix_world_news_item_news_type ON world_news_item (news_type);
CREATE INDEX IF NOT EXISTS ix_world_news_item_source_type ON world_news_item (source_type);
CREATE INDEX IF NOT EXISTS ix_world_news_item_status ON world_news_item (status);
