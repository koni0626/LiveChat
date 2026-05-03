ALTER TABLE user ADD COLUMN points_balance INTEGER NOT NULL DEFAULT 3000;

CREATE TABLE IF NOT EXISTS point_transaction (
    id INTEGER NOT NULL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    project_id INTEGER,
    action_type VARCHAR(100) NOT NULL,
    points_delta INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'success',
    session_id INTEGER,
    message_id INTEGER,
    image_id INTEGER,
    detail_json TEXT,
    created_at DATETIME NOT NULL,
    FOREIGN KEY(user_id) REFERENCES user (id),
    FOREIGN KEY(project_id) REFERENCES project (id),
    FOREIGN KEY(session_id) REFERENCES chat_session (id),
    FOREIGN KEY(message_id) REFERENCES chat_message (id),
    FOREIGN KEY(image_id) REFERENCES session_image (id)
);

CREATE INDEX IF NOT EXISTS ix_point_transaction_user_id ON point_transaction (user_id);
CREATE INDEX IF NOT EXISTS ix_point_transaction_project_id ON point_transaction (project_id);
CREATE INDEX IF NOT EXISTS ix_point_transaction_action_type ON point_transaction (action_type);
CREATE INDEX IF NOT EXISTS ix_point_transaction_status ON point_transaction (status);
CREATE INDEX IF NOT EXISTS ix_point_transaction_session_id ON point_transaction (session_id);
CREATE INDEX IF NOT EXISTS ix_point_transaction_message_id ON point_transaction (message_id);
CREATE INDEX IF NOT EXISTS ix_point_transaction_image_id ON point_transaction (image_id);
