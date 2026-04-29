CREATE TABLE IF NOT EXISTS outing_session (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'active',
    current_step INTEGER NOT NULL DEFAULT 0,
    max_steps INTEGER NOT NULL DEFAULT 3,
    mood VARCHAR(100),
    summary TEXT,
    memory_title VARCHAR(255),
    memory_summary TEXT,
    state_json TEXT,
    completed_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    deleted_at DATETIME,
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(character_id) REFERENCES character (id),
    FOREIGN KEY(location_id) REFERENCES world_location (id)
);

CREATE INDEX IF NOT EXISTS ix_outing_session_project_id ON outing_session (project_id);
CREATE INDEX IF NOT EXISTS ix_outing_session_user_id ON outing_session (user_id);
CREATE INDEX IF NOT EXISTS ix_outing_session_character_id ON outing_session (character_id);
CREATE INDEX IF NOT EXISTS ix_outing_session_location_id ON outing_session (location_id);
CREATE INDEX IF NOT EXISTS ix_outing_session_status ON outing_session (status);
