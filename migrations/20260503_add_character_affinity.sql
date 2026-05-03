ALTER TABLE character_user_memory ADD COLUMN affinity_score INTEGER NOT NULL DEFAULT 0;
ALTER TABLE character_user_memory ADD COLUMN affinity_label VARCHAR(80);
ALTER TABLE character_user_memory ADD COLUMN affinity_notes TEXT;
ALTER TABLE character_user_memory ADD COLUMN physical_closeness_level INTEGER NOT NULL DEFAULT 0;
