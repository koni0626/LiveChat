ALTER TABLE story ADD COLUMN default_outfit_id INTEGER REFERENCES character_outfit(id);
CREATE INDEX IF NOT EXISTS ix_story_default_outfit_id ON story(default_outfit_id);
