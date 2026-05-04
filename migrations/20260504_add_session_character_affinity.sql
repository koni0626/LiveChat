CREATE TABLE IF NOT EXISTS session_character_affinity (
    id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    affinity_score INTEGER NOT NULL DEFAULT 0,
    affinity_label VARCHAR(80),
    affinity_notes TEXT,
    physical_closeness_level INTEGER NOT NULL DEFAULT 0,
    locked_at_100 BOOLEAN NOT NULL DEFAULT 0,
    reached_100_at DATETIME,
    last_interaction_at DATETIME,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_session_character_affinity_session_character UNIQUE (session_id, character_id),
    FOREIGN KEY(session_id) REFERENCES chat_session (id),
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(character_id) REFERENCES character (id)
);

CREATE INDEX IF NOT EXISTS ix_session_character_affinity_session_id ON session_character_affinity (session_id);
CREATE INDEX IF NOT EXISTS ix_session_character_affinity_user_id ON session_character_affinity (user_id);
CREATE INDEX IF NOT EXISTS ix_session_character_affinity_project_id ON session_character_affinity (project_id);
CREATE INDEX IF NOT EXISTS ix_session_character_affinity_character_id ON session_character_affinity (character_id);
