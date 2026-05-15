CREATE TABLE IF NOT EXISTS blog_post (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    created_by_user_id INTEGER NOT NULL,
    theme VARCHAR(255) NOT NULL,
    instruction TEXT,
    body TEXT NOT NULL,
    thumbnail_asset_id INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'draft',
    generation_state_json TEXT,
    published_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME,
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(character_id) REFERENCES character (id),
    FOREIGN KEY(created_by_user_id) REFERENCES user (id),
    FOREIGN KEY(thumbnail_asset_id) REFERENCES asset (id)
);

CREATE INDEX IF NOT EXISTS ix_blog_post_project_id ON blog_post (project_id);
CREATE INDEX IF NOT EXISTS ix_blog_post_character_id ON blog_post (character_id);
CREATE INDEX IF NOT EXISTS ix_blog_post_created_by_user_id ON blog_post (created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_blog_post_status ON blog_post (status);

CREATE TABLE IF NOT EXISTS blog_x_schedule (
    id INTEGER PRIMARY KEY,
    blog_post_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    created_by_user_id INTEGER NOT NULL,
    scheduled_for DATETIME NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'scheduled',
    x_post_id VARCHAR(100),
    error_message TEXT,
    metadata_json TEXT,
    posted_at DATETIME,
    cancelled_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    FOREIGN KEY(blog_post_id) REFERENCES blog_post (id),
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(created_by_user_id) REFERENCES user (id)
);

CREATE INDEX IF NOT EXISTS ix_blog_x_schedule_blog_post_id ON blog_x_schedule (blog_post_id);
CREATE INDEX IF NOT EXISTS ix_blog_x_schedule_project_id ON blog_x_schedule (project_id);
CREATE INDEX IF NOT EXISTS ix_blog_x_schedule_created_by_user_id ON blog_x_schedule (created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_blog_x_schedule_scheduled_for ON blog_x_schedule (scheduled_for);
CREATE INDEX IF NOT EXISTS ix_blog_x_schedule_status ON blog_x_schedule (status);
