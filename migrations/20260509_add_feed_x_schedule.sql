CREATE TABLE IF NOT EXISTS feed_x_schedule (
    id INTEGER PRIMARY KEY,
    feed_post_id INTEGER NOT NULL,
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
    FOREIGN KEY(feed_post_id) REFERENCES feed_post (id),
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(created_by_user_id) REFERENCES user (id)
);

CREATE INDEX IF NOT EXISTS ix_feed_x_schedule_feed_post_id ON feed_x_schedule (feed_post_id);
CREATE INDEX IF NOT EXISTS ix_feed_x_schedule_project_id ON feed_x_schedule (project_id);
CREATE INDEX IF NOT EXISTS ix_feed_x_schedule_created_by_user_id ON feed_x_schedule (created_by_user_id);
CREATE INDEX IF NOT EXISTS ix_feed_x_schedule_scheduled_for ON feed_x_schedule (scheduled_for);
CREATE INDEX IF NOT EXISTS ix_feed_x_schedule_status ON feed_x_schedule (status);
