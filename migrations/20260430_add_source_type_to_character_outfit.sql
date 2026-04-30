ALTER TABLE character_outfit ADD COLUMN source_type VARCHAR(50) NOT NULL DEFAULT 'outfit';
CREATE INDEX IF NOT EXISTS ix_character_outfit_source_type ON character_outfit(source_type);
UPDATE character_outfit
SET source_type = 'character_base'
WHERE name = '基準画像'
   OR asset_id IN (
        SELECT base_asset_id
        FROM character
        WHERE base_asset_id IS NOT NULL
   );
