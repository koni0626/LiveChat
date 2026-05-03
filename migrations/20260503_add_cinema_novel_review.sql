CREATE TABLE IF NOT EXISTS cinema_novel_review (
    id INTEGER PRIMARY KEY,
    novel_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    feed_post_id INTEGER,
    memory_note_id INTEGER,
    review_text TEXT NOT NULL,
    memory_note TEXT,
    rating_label VARCHAR(80),
    status VARCHAR(50) NOT NULL DEFAULT 'published',
    metadata_json TEXT,
    created_at DATETIME,
    updated_at DATETIME,
    deleted_at DATETIME,
    CONSTRAINT uq_cinema_novel_review_novel_character_user UNIQUE (novel_id, character_id, user_id),
    FOREIGN KEY(novel_id) REFERENCES cinema_novel (id),
    FOREIGN KEY(character_id) REFERENCES character (id),
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(feed_post_id) REFERENCES feed_post (id),
    FOREIGN KEY(memory_note_id) REFERENCES character_memory_note (id)
);

CREATE INDEX IF NOT EXISTS ix_cinema_novel_review_novel_id ON cinema_novel_review (novel_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_review_character_id ON cinema_novel_review (character_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_review_user_id ON cinema_novel_review (user_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_review_feed_post_id ON cinema_novel_review (feed_post_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_review_memory_note_id ON cinema_novel_review (memory_note_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_review_status ON cinema_novel_review (status);
