CREATE TABLE IF NOT EXISTS cinema_novel_lore_entry (
    id INTEGER NOT NULL PRIMARY KEY,
    novel_id INTEGER NOT NULL,
    lore_type VARCHAR(50) NOT NULL DEFAULT 'other',
    name VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    role_note TEXT,
    source_note TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME,
    FOREIGN KEY(novel_id) REFERENCES cinema_novel (id),
    CONSTRAINT uq_cinema_novel_lore_entry_novel_type_name UNIQUE (novel_id, lore_type, name)
);

CREATE INDEX IF NOT EXISTS ix_cinema_novel_lore_entry_lore_type ON cinema_novel_lore_entry (lore_type);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_lore_entry_novel_id ON cinema_novel_lore_entry (novel_id);

CREATE TABLE IF NOT EXISTS cinema_novel_character_impression (
    id INTEGER NOT NULL PRIMARY KEY,
    novel_id INTEGER NOT NULL,
    reviewer_character_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    target_name VARCHAR(255) NOT NULL,
    target_character_id INTEGER,
    impression_text TEXT NOT NULL,
    talk_hint TEXT,
    memory_note_id INTEGER,
    metadata_json TEXT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME,
    FOREIGN KEY(memory_note_id) REFERENCES character_memory_note (id),
    FOREIGN KEY(novel_id) REFERENCES cinema_novel (id),
    FOREIGN KEY(reviewer_character_id) REFERENCES character (id),
    FOREIGN KEY(target_character_id) REFERENCES character (id),
    FOREIGN KEY(user_id) REFERENCES user (id),
    CONSTRAINT uq_cinema_novel_character_impression_unique_target UNIQUE (novel_id, reviewer_character_id, user_id, target_name)
);

CREATE INDEX IF NOT EXISTS ix_cinema_novel_character_impression_memory_note_id ON cinema_novel_character_impression (memory_note_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_character_impression_novel_id ON cinema_novel_character_impression (novel_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_character_impression_reviewer_character_id ON cinema_novel_character_impression (reviewer_character_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_character_impression_target_character_id ON cinema_novel_character_impression (target_character_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_character_impression_user_id ON cinema_novel_character_impression (user_id);
