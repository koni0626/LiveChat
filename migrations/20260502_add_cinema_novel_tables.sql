CREATE TABLE IF NOT EXISTS cinema_novel (
    id INTEGER NOT NULL PRIMARY KEY,
    project_id INTEGER NOT NULL,
    created_by_user_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    subtitle VARCHAR(255),
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    mode VARCHAR(80) NOT NULL DEFAULT 'cinema_novel',
    cover_asset_id INTEGER,
    poster_asset_id INTEGER,
    source_path VARCHAR(512),
    production_json TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME,
    deleted_at DATETIME,
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(created_by_user_id) REFERENCES user (id),
    FOREIGN KEY(cover_asset_id) REFERENCES asset (id),
    FOREIGN KEY(poster_asset_id) REFERENCES asset (id)
);

CREATE INDEX IF NOT EXISTS ix_cinema_novel_project_id ON cinema_novel (project_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_created_by_user_id ON cinema_novel (created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_status ON cinema_novel (status);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_mode ON cinema_novel (mode);

CREATE TABLE IF NOT EXISTS cinema_novel_chapter (
    id INTEGER NOT NULL PRIMARY KEY,
    novel_id INTEGER NOT NULL,
    chapter_no INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    body_markdown TEXT,
    scene_json TEXT,
    cover_asset_id INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME,
    deleted_at DATETIME,
    FOREIGN KEY(novel_id) REFERENCES cinema_novel (id),
    FOREIGN KEY(cover_asset_id) REFERENCES asset (id)
);

CREATE INDEX IF NOT EXISTS ix_cinema_novel_chapter_novel_id ON cinema_novel_chapter (novel_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_chapter_chapter_no ON cinema_novel_chapter (chapter_no);

CREATE TABLE IF NOT EXISTS cinema_novel_progress (
    id INTEGER NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    novel_id INTEGER NOT NULL,
    chapter_id INTEGER NOT NULL,
    scene_index INTEGER NOT NULL DEFAULT 0,
    page_index INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(novel_id) REFERENCES cinema_novel (id),
    FOREIGN KEY(chapter_id) REFERENCES cinema_novel_chapter (id),
    CONSTRAINT uq_cinema_novel_progress_user_novel UNIQUE (user_id, novel_id)
);

CREATE INDEX IF NOT EXISTS ix_cinema_novel_progress_user_id ON cinema_novel_progress (user_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_progress_novel_id ON cinema_novel_progress (novel_id);
CREATE INDEX IF NOT EXISTS ix_cinema_novel_progress_chapter_id ON cinema_novel_progress (chapter_id);
