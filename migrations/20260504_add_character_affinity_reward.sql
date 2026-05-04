CREATE TABLE IF NOT EXISTS character_affinity_reward (
    id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    character_id INTEGER NOT NULL,
    event_image_id INTEGER,
    event_claimed_at DATETIME,
    costume_ticket_balance INTEGER NOT NULL DEFAULT 0,
    costume_ticket_earned_at DATETIME,
    costume_ticket_used_at DATETIME,
    lccd_unlocked_session_id INTEGER,
    saved_outfit_id INTEGER,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_character_affinity_reward_user_character UNIQUE (user_id, character_id),
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(character_id) REFERENCES character (id),
    FOREIGN KEY(event_image_id) REFERENCES session_image (id),
    FOREIGN KEY(lccd_unlocked_session_id) REFERENCES chat_session (id),
    FOREIGN KEY(saved_outfit_id) REFERENCES character_outfit (id)
);

CREATE INDEX IF NOT EXISTS ix_character_affinity_reward_user_id ON character_affinity_reward (user_id);
CREATE INDEX IF NOT EXISTS ix_character_affinity_reward_project_id ON character_affinity_reward (project_id);
CREATE INDEX IF NOT EXISTS ix_character_affinity_reward_character_id ON character_affinity_reward (character_id);
CREATE INDEX IF NOT EXISTS ix_character_affinity_reward_lccd_unlocked_session_id
    ON character_affinity_reward (lccd_unlocked_session_id);
